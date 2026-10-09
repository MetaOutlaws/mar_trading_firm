"""Fixed entry features, historical-only lead nomination and bounded path anatomy."""
import numpy as np
import pandas as pd
FEATURES=('volume_ratio','prior_atr_pct','extension_atr','aligned_rsi14','aligned_crsi',
          'aligned_btc24','aligned_own24','efficiency24_before_signal','adx14',
          'compression','signal_tr_atr','aligned_body_atr')
KEYS=['partition','symbol','side','signal_i']

def auc(x,y):
    x=np.asarray(x,float);y=np.asarray(y,bool)
    if not np.isfinite(x).all():raise ValueError('missing feature')
    a=x[y];b=x[~y]
    return float(((a[:,None]>b).sum()+.5*(a[:,None]==b).sum())/(len(a)*len(b))) if len(a)*len(b) else np.nan

def stats(q):
    v=q.net_return
    return dict(n=len(q),wins=int((v>0).sum()),losses=int((v<0).sum()),stops=int((q.reason=='stop').sum()),
                targets=int((q.reason=='target').sum()),mean_net=float(v.mean()) if len(q) else np.nan,
                win_rate=float((v>0).mean()) if len(q) else np.nan)

def mask(q,feature,threshold,direction):
    if direction not in ['lower','upper']:raise ValueError(direction)
    if not np.isfinite(q[feature]).all():raise ValueError('missing feature')
    low=q[feature]<=threshold
    return low if direction=='lower' else ~low

def nominate(frame):
    q=frame[frame.partition=='historical'].copy()
    if not len(q):raise ValueError('no historical trades')
    rows=[]
    for feature in FEATURES:
        threshold=float(q[feature].median());rank=auc(q[feature],q.net_return>0)
        for direction in ['lower','upper']:
            keep=mask(q,feature,threshold,direction);a=q[keep];b=q[~keep]
            delta=float(a.net_return.mean()-b.net_return.mean())
            leave=[]
            for symbol in ['BTCUSDT','ETHUSDT','SOLUSDT']:
                aa=a[a.symbol!=symbol];bb=b[b.symbol!=symbol]
                leave.append(float(aa.net_return.mean()-bb.net_return.mean()) if len(aa)*len(bb) else np.nan)
            oriented=rank if direction=='upper' else 1-rank
            passes=bool(len(a)>=12 and len(b)>=12 and a.net_return.mean()>0 and delta>0
                        and oriented>.5 and np.isfinite(leave).all() and min(leave)>0)
            rows.append(dict(feature=feature,direction=direction,threshold=threshold,retained=len(a),excluded=len(b),
                retained_mean=a.net_return.mean(),excluded_mean=b.net_return.mean(),difference=delta,oriented_auc=oriented,
                leave_BTC_difference=leave[0],leave_ETH_difference=leave[1],leave_SOL_difference=leave[2],
                minimum_leave_token_difference=min(leave),eligible=passes))
    candidates=pd.DataFrame(rows).sort_values(['eligible','minimum_leave_token_difference','difference','feature','direction'],
        ascending=[False,False,False,True,True],kind='stable').reset_index(drop=True)
    eligible=candidates[candidates.eligible]
    selection=dict(status='nominated' if len(eligible) else 'none',basis='historical_only',historical_n=len(q),
                   later_associations_scored=False,automatic_deployment=False)
    if len(eligible):selection.update(eligible.iloc[0].to_dict())
    return candidates,selection

def path_anatomy(c,row):
    i,j=int(row.entry_i),int(row.exit_i)
    if row.fund_mode!='open' or j<=i:raise ValueError('exact sampled path required')
    high=max(float(c.high.iloc[i:j].max()),float(row.quote))
    low=min(float(c.low.iloc[i:j].min()),float(row.quote))
    e=float(row.entry_price)
    mfe=max(0.,high/e-1 if row.side==1 else 1-low/e)
    mae=max(0.,1-low/e if row.side==1 else high/e-1)
    return dict(mfe=mfe,mae=mae,holding_minutes=j-i)
