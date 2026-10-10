from analysis_lib import *
from concurrent.futures import ProcessPoolExecutor,as_completed

RECIPES=[f'T{i:02d}' for i in range(8)]

def window(r,recipe):
    if recipe in ['T00','T07']:return 60
    if recipe in ['T01','T02','T03','T04']:return {'T01':15,'T02':30,'T03':120,'T04':240}[recipe]
    fast=r.prior_atr/r.close>=.02
    return (30 if fast else 120) if recipe=='T05' else (120 if fast else 30)

def plan(h,l,cl,i,side,boundary,w):
    end=min(i+w,len(cl)-1)
    touch=(l[i:end]<=boundary) if side==1 else (h[i:end]>=boundary)
    confirmed=np.maximum.accumulate(touch)&(side*(cl[i:end]-boundary)>0) if len(touch) else touch
    hits=np.flatnonzero(confirmed)
    return (i+int(hits[0])+1,'filled') if len(hits) else (-1,'no_reclaim' if touch.any() else 'no_touch')

def independent_plan(h,l,cl,i,side,boundary,w):
    touched=False
    for k in range(i,min(i+w,len(cl)-1)):
        touched=touched or (l[k]<=boundary if side==1 else h[k]>=boundary)
        if touched and side*(cl[k]-boundary)>0:return k+1
    return -1

def fixtures():
    h=np.array([102.,102.,102.,102.]);l=np.array([101.,100.,99.,99.]);cl=np.array([101.,100.,101.,101.])
    assert plan(h,l,cl,0,1,100.,2)[0]==-1 # boundary equality is not strict reclaim
    assert plan(h,l,cl,0,1,100.,3)[0]==3 # last completed minute of window can fill next open
    assert plan(h,l,cl,0,1,100.,9)[0]==3
    assert plan(h,l,np.array([101.,100.,100.,101.]),0,1,100.,9)[0]==-1 # last close has no next open
    assert plan(np.array([101.,101.,101.]),np.array([99.,99.,99.]),np.array([99.,99.,99.]),0,-1,100.,1)[0]==1
    return 5

def token(symbol):
    e,s=inputs();s=s[s.symbol==symbol];e=e[e.symbol==symbol]
    c,f,arr,f0,f1=legacy.load_tape(symbol);o,h,l,cl=arr
    assert c.index.max()<pd.Timestamp('2026-01-01',tz='UTC')
    old=pd.read_parquet(BASE/'mar_protection_surface_20261010/grid'/f'{symbol}.parquet') if len(e) else pd.DataFrame()
    cuts=[(y,int(np.searchsorted(c.index.asi8,pd.Timestamp(f'{y+1}-01-01',tz='UTC').value)-1)) for y in [2022,2023,2024]]
    paths=[];plans=[];check=0;cash=0;parity=0
    for r in s.itertuples():
        i0=int(r.signal_i);assert c.index[i0]==r.signal_time
        oldentry=e[(e.side==r.side)&(e.signal_i==i0)]
        for recipe in RECIPES:
            w=window(r,recipe);i,status=plan(h,l,cl,i0,r.side,r.entry_boundary,w)
            assert i==independent_plan(h,l,cl,i0,r.side,r.entry_boundary,w);check+=1
            planned=i
            # A newly arrived opposite signal means strictly after original signal,
            # up to and including the pending fill's open. Earlier signals cannot cancel retrospectively.
            opposite=s[(s.side==-r.side)&(s.signal_time>r.signal_time)&(s.signal_time<=c.index[i])] if i>=0 else s.iloc[:0]
            if recipe=='T07' and len(opposite):i=-1;status='opposite_signal_cancelled'
            plans.append(dict(sid=r.sid,symbol=symbol,recipe=recipe,window_minutes=w,entry_i=i,planned_entry_i=planned,status=status,opposite_signals_before_fill=len(opposite),high_vol=r.high_vol,signal_time=r.signal_time))
            if recipe=='T00':
                assert (i>=0)==bool(len(oldentry))
                if i>=0:assert i==int(oldentry.entry_i.iloc[0]);parity+=1
            if i<0:continue
            for slip in [.002,.003]:
                ep=o[i]*(1+r.side*slip);stop=3*r.prior_atr/ep;target=4*r.prior_atr/ep
                result=simulate(o,cl,f0,i,int(r.side),slip,stop,target,0,0.,0.,0.,0.)
                independent(o,cl,f0,i,int(r.side),slip,stop,target,0,0.,0.,0.,0.,result)
                row=settle(c,f0,f1,o,i,int(r.side),slip,stop,result,0.,cuts)
                if (r.sid+int(recipe[1:]))%11==0:direct_cash(c,f,o,row,int(r.side),slip);cash+=1
                if recipe=='T00':
                    prior=old[(old.eid==int(oldentry.eid.iloc[0]))&(old.policy==284)&(old.slippage==slip)].iloc[0]
                    for key in ['exit_i','net_return','entry_price','risk_scale']:assert abs(row[key]-prior[key])<1e-12
                paths.append(row|dict(sid=r.sid,symbol=symbol,side=r.side,signal_i=i0,signal_time=r.signal_time,entry=c.index[i],year=r.year,high_vol=r.high_vol,population=r.population,sector=r.sector,recipe=recipe,slippage=slip,window_minutes=w,entry_delay_minutes=i-i0,fill_distance_ATR=r.side*(o[i]-r.entry_boundary)/r.prior_atr,unreachable_before_target=False))
    pd.DataFrame(paths).to_parquet(ROOT/'paths'/f'{symbol}_paths.parquet',index=False,compression='zstd')
    pd.DataFrame(plans).to_parquet(ROOT/'paths'/f'{symbol}_plans.parquet',index=False)
    return dict(symbol=symbol,paths=len(paths),entry_checks=check,control_entries=parity,cash_checks=cash)

def freeze():
    assert not (ROOT/'FREEZE.json').exists()
    proto=json.loads((BASE/'mar_overnight_research_20261010/STAGE3_FREEZE.json').read_text())
    assert hashlib.sha256((ROOT/'PROTOCOL.md').read_bytes()).hexdigest()==proto['protocol_sha256']
    files=[ROOT/'run_paths.py',ROOT/'analysis_lib.py',BASE/'mar_protection_surface_20261010/sources.parquet',BASE/'mar_protection_surface_20261010/simulator.py']
    write('FREEZE.json',dict(protocol_sha256=proto['protocol_sha256'],original_protocol_freeze=proto,frozen_at_task_time='2026-10-10T02:20:46+04:00',paths_opened=False,recipe_ids=RECIPES,clarification='new opposite arrival is (signal_time, planned_fill_time]; no retrospective cancellation',sha256={str(p.relative_to(BASE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}))

def run():
    for p,h in json.loads((ROOT/'FREEZE.json').read_text())['sha256'].items():assert hashlib.sha256((BASE/p).read_bytes()).hexdigest()==h
    tests=fixtures();(ROOT/'paths').mkdir(exist_ok=False);_,s=inputs();checks=[]
    with ProcessPoolExecutor(max_workers=3) as pool:
        for job in as_completed([pool.submit(token,x) for x in sorted(s.symbol.unique())]):
            a=job.result();checks.append(a);print('TOKEN',len(checks),a,flush=True)
    assert sum(x['entry_checks'] for x in checks)==1026*8 and sum(x['control_entries'] for x in checks)==530
    write('PATH_VERIFICATION.json',dict(status='pass',tokens=len(checks),source_signals=1026,paths=sum(x['paths'] for x in checks),independent_entry_checks=sum(x['entry_checks'] for x in checks),control_entries=sum(x['control_entries'] for x in checks),direct_cash_checks=sum(x['cash_checks'] for x in checks),boundary_fixtures=tests,reserved_2026_opened=False))

if __name__=='__main__':
    if '--freeze' in sys.argv:freeze()
    else:run()
