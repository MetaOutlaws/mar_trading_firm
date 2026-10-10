from common import *

KINDS={'none':0,'breakeven':1,'floor':2,'trail':3,'partial_original':4,'partial_trail':5}

@njit(cache=True)
def simulate(o,cl,f0,i,side,slip,stop,target,kind,trigger,distance,floor,partial):
    ep=o[i]*(1+side*slip);level=-stop;best=0.;armed=False;trigger_i=-1;part_i=-1;pending=-1
    for j in range(i+1,len(o)):
        move=side*(o[j]/ep-1)
        if side*(o[j]-ep*(1+side*level))<=0:return j,o[j],4 if level>-stop+1e-12 else 1,part_i,int(armed),trigger_i
        if side*(o[j]-ep*(1+side*target))>=0:return j,o[j],2,part_i,int(armed),trigger_i
        if pending==j:part_i=j;pending=-1
        best=max(best,move)
        if kind==1 or kind==2:
            accrued=side*(f0[j]-f0[i])/ep
            candidate=side*((side+FEE+accrued+floor)/(side-FEE)-1)
            if not armed and best>=trigger and (kind==1 or move>candidate):armed=True;trigger_i=j
            if armed:level=max(level,candidate)
        elif kind==3:
            if not armed and best>=trigger:armed=True;trigger_i=j
            if armed:level=max(level,best-distance)
        elif kind>=4:
            if not armed and best>=trigger:armed=True;trigger_i=j;pending=j+1
            if kind==5 and part_i>=0:level=max(level,best-distance)
    return len(o)-1,cl[-1],3,part_i,int(armed),trigger_i

def independent(o,cl,f0,i,side,slip,stop,target,kind,trigger,distance,floor,partial,result):
    j,quote,reason,part_i,armed,trigger_i=result;ep=o[i]*(1+side*slip)
    x=o[i+1:j+1];move=side*(x/ep-1);peak=np.maximum.accumulate(np.maximum(move,0));effective=np.full(len(x),-stop)
    hit=np.flatnonzero(peak>=trigger) if kind else np.array([],int)
    trigger_local=int(hit[0]) if len(hit) else -1;part_local=-1
    if kind in [1,2]:
        cost=side*(f0[i+1:j+1]-f0[i])/ep
        floorlevel=side*((side+FEE+cost+floor)/(side-FEE)-1)
        eligible=(peak>=trigger)&((move>floorlevel) if kind==2 else True)
        activated=np.maximum.accumulate(eligible);hit=np.flatnonzero(eligible);trigger_local=int(hit[0]) if len(hit) else -1
        decided=np.maximum.accumulate(np.where(activated,np.maximum(floorlevel,-stop),-stop))
        effective=np.r_[-stop,decided[:-1]]
    elif kind==3:
        decided=np.maximum.accumulate(np.where(peak>=trigger,np.maximum(peak-distance,-stop),-stop));effective=np.r_[-stop,decided[:-1]]
    elif kind>=4 and trigger_local>=0:
        part_local=trigger_local+1
        if kind==5:
            active=np.arange(len(x))>=part_local
            decided=np.maximum.accumulate(np.where(active,np.maximum(peak-distance,-stop),-stop));effective=np.r_[-stop,decided[:-1]]
    stops=side*(x-ep*(1+side*effective))<=0;targets=side*(x-ep*(1+side*target))>=0
    exits=np.flatnonzero(stops|targets)
    if reason==3:assert not len(exits) and j==len(o)-1 and quote==cl[-1]
    else:
        assert len(exits) and int(exits[0])+i+1==j
        expected=(4 if effective[-1]>-stop+1e-12 else 1) if stops[-1] else 2
        assert reason==expected and quote==o[j]
    # A decision on a full-exit open never occurs; terminal close permits it.
    can_decide=len(move)-(reason!=3)
    exp_trigger=i+1+trigger_local if 0<=trigger_local<can_decide else -1
    assert trigger_i==exp_trigger and armed==int(exp_trigger>=0)
    expected_part=i+1+part_local if kind>=4 and 0<=part_local<can_decide else -1
    assert part_i==expected_part

def settle(c,f0,f1,o,i,side,slip,stop,result,partial,cutoffs=None):
    j,quote,reason,part_i,armed,trigger_i=result;ep=o[i]*(1+side*slip)
    xp=quote if reason in [1,4] else quote*(1-side*slip)
    fullfund=side*((f1[j] if reason==3 else f0[j])-f0[i])/ep
    fullfee=FEE*(1+xp/ep);fullgross=side*(xp/ep-1);q=partial if part_i>=0 else 0.
    px=o[part_i]*(1-side*slip) if q else np.nan
    pfund=side*(f0[part_i]-f0[i])/ep if q else 0.;pfee=FEE*(1+px/ep) if q else 0.;pgross=side*(px/ep-1) if q else 0.
    fees=q*pfee+(1-q)*fullfee;fund=q*pfund+(1-q)*fullfund;gross=q*pgross+(1-q)*fullgross;net=gross-fees-fund
    row=dict(entry_i=i,exit_i=j,exit_ns=c.index[j].value,reason=reason,partial_i=part_i,partial_fraction=q,entry_price=ep,exit_price=xp,
        partial_price=px,activated=bool(armed),trigger_i=trigger_i,stop_pct=stop,fees=fees,funding=fund,gross_return=gross,net_return=net,
        net_R=net/stop,risk_scale=.02/stop,holding_minutes=j-i+(reason==3))
    if cutoffs is None:cutoffs=[(year,int(np.searchsorted(c.index.asi8,pd.Timestamp(f'{year+1}-01-01',tz='UTC').value)-1)) for year in [2022,2023,2024]]
    for year,k in cutoffs:
        if k<i:value=0.
        elif j<=k:value=net
        else:
            used=q if q and part_i<=k else 0.
            mx=c.close.iloc[k]*(1-side*slip);mf=side*(f1[k]-f0[i])/ep
            value=used*(pgross-pfee-pfund)+(1-used)*(side*(mx/ep-1)-FEE*(1+mx/ep)-mf)
        row[f'mark_{year}']=value
    return row

def direct_cash(c,f,o,row,side,slip):
    i=row['entry_i'];ep=row['entry_price'];j=row['exit_i'];q=row['partial_fraction'];k=row['partial_i']
    def leg(end,price,close=False):
        t=c.index[end]+(pd.Timedelta(minutes=1) if close else pd.Timedelta(0))
        events=f[(f.index>c.index[i])&(f.index<=t)]
        ix=c.index.get_indexer(events.index.floor('min'),method='pad')
        fund=side*np.sum(events.funding_rate.to_numpy()*o[np.clip(ix,0,len(o)-1)])/ep
        return side*(price/ep-1)-FEE*(1+price/ep)-fund,fund
    v,fu=leg(j,row['exit_price'],row['reason']==3)
    if q:
        pv,pf=leg(k,row['partial_price']);v=(1-q)*v+q*pv;fu=(1-q)*fu+q*pf
        assert k>row['trigger_i'] and i<k<=j and 0<q<1
    assert abs(v-row['net_return'])<1e-10 and abs(fu-row['funding'])<1e-10
