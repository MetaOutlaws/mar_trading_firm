"""Read copied cache only. Reproduce 96 baseline cells and expose fixed-path costs.
No new strategies, live access, approvals, or 2026 return evaluation.
"""
import argparse, hashlib, json, sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import study

def decompose(t,slip):
    t=t.copy()
    if t.empty:return t
    d=t.side
    eq=t.entry_price/(1+d*slip)
    xq=t.exit_price/(1-d*slip)
    t['quoted_path_return']=d*(xq-eq)/eq
    t['slippage_drag']=t.quoted_path_return-t.gross_return
    residual=t.quoted_path_return-t.slippage_drag-t.fees-t.funding-t.net_return
    if not np.allclose(residual,0,atol=1e-12):raise ValueError('Cost decomposition mismatch')
    # Quoted path is a decomposition of original exits, NOT a zero-cost rerun.
    t['break_even_total_cost']=t.quoted_path_return
    return t

def metrics(t):
    s=study.score(t)
    if t.empty:return s
    for c in ('quoted_path_return','slippage_drag','fees','funding','net_return'):
        s['mean_'+c]=float(t[c].mean())
    for reason in ('stop','target','time'):
        q=t.loc[t.reason==reason]
        s[reason+'_fraction']=len(q)/len(t)
        s[reason+'_mean_net']=float(q.net_return.mean()) if len(q) else None
    return s

def run(cache,out):
    out.mkdir(parents=True,exist_ok=False)
    manifest={'status':'auditing','source_study_sha256':hashlib.sha256(Path(study.__file__).read_bytes()).hexdigest(),
              'scope':'discovery and validation only; no 2026 returns','inputs':{},'approval':'NONE'}
    rows=[];quarters=[]
    try:
        for sym in study.SYMBOLS:
            cp=cache/f'{sym}_1m.parquet';fp=cache/'funding'/f'{sym}_funding.parquet'
            c=study.load(cp);f=study.load(fp,True)
            manifest['inputs'][sym]={'audit':study.audit(c,f),'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (cp,fp)}}
            # Cut future candles and funding before any signals or return diagnostics.
            cutoff=study.PARTS['validation'][1]
            c=c.loc[(c.index>=study.START)&(c.index<cutoff)]
            f=f.loc[f.index<=cutoff]
            tape=study.Tape(c,f);signals=study.signals(c)
            slip=.001 if sym=='SOLUSDT' else .0005
            for cid,(family,side,tp,sl) in enumerate(study.CONFIGS):
                for part in ('discovery','validation'):
                    t=decompose(tape.run(signals[family,side],side,tp,sl,slip,*study.PARTS[part]),slip)
                    key={'symbol':sym,'config_id':cid,'family':family,'side':side,'target':tp,'stop':sl,'partition':part}
                    rows.append({**key,**metrics(t)})
                    if not t.empty:
                        t.to_csv(out/f'{sym}_{cid}_{part}_trades.csv.gz',index=False)
                        labels=t.entry.dt.strftime('%Y')+'Q'+t.entry.dt.quarter.astype(str)
                        for quarter,q in t.groupby(labels):quarters.append({**key,'quarter':quarter,**metrics(q)})
            print(sym,'completed',flush=True)
        pd.DataFrame(rows).to_csv(out/'cost_decomposition_96_cells.csv',index=False)
        pd.DataFrame(quarters).to_csv(out/'quarterly_diagnostics.csv',index=False)
        manifest['status']='diagnostics_complete'
    except Exception as exc:
        manifest.update(status='blocked',error=str(exc))
        raise
    finally:(out/'diagnostic_manifest.json').write_text(json.dumps(manifest,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();run(a.cache,a.out)
