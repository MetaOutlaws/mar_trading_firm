"""Frozen quote-only exit sampling on UTC minute grids; no between-poll memory."""
from numbers import Integral
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'hourly_fill_brackets_20261008'))
from bracket_rule import levels,raw_trade,independent_path,STOP
POLLS=(0,1,5,15)  # 0 means the original intrabar comparator, not zero-second polling.
PRIMARY_POLL=1

def sample_indices(index,i,end,poll):
    if isinstance(poll,bool) or not isinstance(poll,Integral) or poll not in (1,5,15):raise ValueError('poll minutes must be 1,5,15')
    if not 0<=i<end<=len(index):raise ValueError('invalid bounds')
    ns=index[i].value
    if ns%60_000_000_000:raise ValueError('entry must be at a UTC minute boundary')
    minute=ns//60_000_000_000
    first=i+poll-minute%poll  # strictly after entry; global clock, not entry-relative.
    return np.arange(first,end,poll,dtype=np.int64)

def poll_trade(t,i,side,slip,end,poll):
    if isinstance(poll,bool) or not isinstance(poll,Integral) or poll not in POLLS:raise ValueError('invalid poll arm')
    if poll==0:r=raw_trade(t,i,side,slip,end,'fill_brackets')
    else:
        x=levels(float(t.o[i]),side,slip,'fill_brackets');ix=sample_indices(t.index,i,end,poll);quotes=t.o[ix]
        stops=side*(quotes-x['stop_price'])<=0;targets=side*(quotes-x['target_price'])>=0
        hits=np.flatnonzero(stops|targets)
        if len(hits):
            k=int(hits[0]);j=int(ix[k]);q=float(quotes[k]);reason='stop' if stops[k] else 'target';mode='open'
        else:j=end-1;q=float(t.cl[j]);reason='boundary_mtm';mode='close'
        r=dict(entry_i=int(i),exit_i=j,quote=q,reason=reason,fund_mode=mode,ambiguous=False,stop_pct=STOP,**x)
    return dict(r,signal_i=int(i),poll_minutes=int(poll))

def verify_path(t,r,side,slip,end,poll):
    if poll==0:return independent_path(t,r,side,slip,end,'fill_brackets')
    i=int(r['entry_i']);anchor=t.o[i]*(1+side*slip);stop=anchor*(1-side*.02);target=anchor*(1+side*.025)
    expected=None
    # Independent sequential clock/predicate implementation, without sample_indices().
    for j in range(i+1,end):
        if (t.index[j].value//60_000_000_000)%poll:continue
        q=float(t.o[j])
        if (q<=stop if side==1 else q>=stop):expected=(j,q,'stop','open');break
        if (q>=target if side==1 else q<=target):expected=(j,q,'target','open');break
    if expected is None:expected=(end-1,float(t.cl[end-1]),'boundary_mtm','close')
    j,q,reason,mode=expected
    assert (r['exit_i'],r['reason'],r['fund_mode'])==(j,reason,mode)
    assert np.isclose(r['quote'],q,atol=1e-12,rtol=0) and not r['ambiguous']
    assert np.isclose(r['stop_price'],stop) and np.isclose(r['target_price'],target)

def independent_cost(c,f,r,side,slip):
    i,j=int(r.entry_i),int(r.exit_i);ep=c.open.iloc[i]*(1+side*slip);xp=r.quote*(1-side*slip)
    def funding(end):
        events=f[(f.index>c.index[i])&(f.index<=end)]
        loc=c.index.get_indexer(events.index,method='pad')
        return side*float(np.sum(events.funding_rate.to_numpy()*c.open.to_numpy()[np.clip(loc,0,len(c)-1)]))/ep
    import pandas as pd
    early=funding(c.index[j]);late=funding(c.index[j]+pd.Timedelta(minutes=1))
    charge=early if r.fund_mode=='open' else late if r.fund_mode=='close' else max(early,late)
    fees=.00055*(1+xp/ep);net=side*(xp/ep-1)-fees-charge
    for key,v in [('entry_price',ep),('exit_price',xp),('fees',fees),('funding',charge),('net_return',net)]:assert np.isclose(getattr(r,key),v,rtol=0,atol=1e-11),key
    assert r.holding_minutes==j-i+(r.fund_mode!='open')
