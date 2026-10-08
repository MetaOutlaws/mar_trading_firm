"""Quote- or fill-anchored barriers; exits and costs otherwise unchanged."""
import numpy as np
STOP=.02;TARGET=.025

def levels(quote,side,slip,arm):
    if side not in [-1,1] or not np.isfinite(quote) or quote<=0 or not np.isfinite(slip) or not 0<=slip<STOP:
        raise ValueError('positive quote, side +/-1 and finite slip in [0,2%) required')
    if arm not in ['quote_brackets','fill_brackets']:raise ValueError(arm)
    fill=quote*(1+side*slip);anchor=quote if arm=='quote_brackets' else fill
    return dict(entry_quote=quote,entry_fill=fill,bracket_anchor=anchor,stop_price=anchor*(1-side*STOP),target_price=anchor*(1+side*TARGET))

def raw_trade(t,i,side,slip,end,arm):
    if not 0<=i<end<=len(t.o):raise ValueError('invalid path bounds')
    x=levels(float(t.o[i]),side,slip,arm);stop,tp=x['stop_price'],x['target_price']
    si=(t.lo if side==1 else t.hi).first(i,end,stop);ti=(t.hi if side==1 else t.lo).first(i,end,tp)
    if si<end and si<=ti:
        j=si;quote=min(stop,t.o[j]) if side==1 else max(stop,t.o[j]);reason='stop';mode='bar';amb=si==ti
    elif ti<end:j=ti;quote=tp;reason='target';mode='bar';amb=False
    else:j=end-1;quote=t.cl[j];reason='boundary_mtm';mode='close';amb=False
    return dict(entry_i=int(i),exit_i=int(j),quote=float(quote),reason=reason,fund_mode=mode,ambiguous=bool(amb),stop_pct=STOP,**x)

def independent_path(t,r,side,slip,end,arm):
    i,j=int(r['entry_i']),int(r['exit_i'])
    # Independently derive thresholds; scan the entire finite path for the first hit.
    anchor=float(t.o[i])*(1+side*slip) if arm=='fill_brackets' else float(t.o[i])
    stop=anchor*(.98 if side==1 else 1.02);target=anchor*(1.025 if side==1 else .975)
    s=t.l[i:end]<=stop if side==1 else t.h[i:end]>=stop
    p=t.h[i:end]>=target if side==1 else t.l[i:end]<=target
    hits=np.flatnonzero(s|p);expected=i+int(hits[0]) if len(hits) else end-1
    assert j==expected
    k=j-i
    if s[k]:reason='stop';quote=min(stop,t.o[j]) if side==1 else max(stop,t.o[j])
    elif p[k]:reason='target';quote=target
    else:reason='boundary_mtm';quote=t.cl[j]
    assert r['reason']==reason and r['ambiguous']==bool(s[k] and p[k])
    assert np.isclose(r['quote'],quote,atol=1e-10,rtol=1e-12)
    assert np.isclose(r['stop_price'],stop,atol=1e-10) and np.isclose(r['target_price'],target,atol=1e-10)
