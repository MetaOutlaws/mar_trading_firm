"""Independent scalar cash audit and calendar bootstrap reconstruction."""
import argparse,hashlib,json,math
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow as pa
pa.set_cpu_count(1);pa.set_io_thread_count(1)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
KEYS=['poll_minutes','partition','stress','symbol','side','signal_i']
CHANGED=['exit_price','gross_return','fees','net_return','slippage_drag','net_R']

def verify(root,cache,runtime):
    e=root/'hourly_stop_cost_20261008';o=e/'results_v1';ref=root/'hourly_exit_polling_20261008/results_v1'
    f=json.loads((o/'freeze.json').read_text());st=json.loads((o/'status.json').read_text());assert st['status']=='complete'
    for group,source in [('sources',root),('inputs',cache),('runtime_sources',runtime),('cached_references',root)]:
        for n,h in f[group].items():assert sha(source/n)==h,n
    for n,h in st['output_hashes'].items():assert sha(o/n)==h,n
    raw=pd.read_parquet(o/'all_opportunities.parquet',use_threads=False);ledger=pd.read_parquet(o/'pooled_ledger.parquet',use_threads=False)
    scalar=0
    for name,allrows in [('all_opportunities.parquet',raw),('pooled_ledger.parquet',ledger)]:
        old=pd.read_parquet(ref/name,use_threads=False).sort_values(KEYS).reset_index(drop=True)
        a=allrows[allrows.cost_model=='research_all_exit_slip'].sort_values(KEYS).reset_index(drop=True)
        b=allrows[allrows.cost_model=='runtime_stop_fill'].sort_values(KEYS).reset_index(drop=True)
        pd.testing.assert_frame_equal(old,a[old.columns],check_exact=True)
        stable=[c for c in old.columns if c not in CHANGED]
        pd.testing.assert_frame_equal(old[stable],b[stable],check_exact=True)
        pd.testing.assert_frame_equal(old.loc[old.reason!='stop'],b.loc[b.reason!='stop',old.columns],check_exact=True)
        for prev,r in zip(old.itertuples(),b.itertuples()):
            fill=r.quote if r.reason=='stop' else prev.exit_price
            profit=fill-r.entry_price if r.side==1 else r.entry_price-fill
            fee=math.fsum([r.entry_price*.00055,fill*.00055])
            net=math.fsum([profit,-fee,-r.funding*r.entry_price])/r.entry_price
            for expected,actual in [(fill,r.exit_price),(profit/r.entry_price,r.gross_return),(fee/r.entry_price,r.fees),(net,r.net_return),(net/.02,r.net_R),(r.quoted_return-profit/r.entry_price,r.slippage_drag)]:
                assert math.isclose(expected,actual,abs_tol=1e-12,rel_tol=0)
            assert r.net_return>=prev.net_return-1e-12
            scalar+=1
    assert not raw.duplicated(KEYS+['cost_model']).any() and not ledger.duplicated(KEYS+['cost_model']).any()
    def select(df,r,model=None):
        q=df[(df.poll_minutes==r.poll_minutes)&(df.partition==r.partition)&(df.stress==r.stress)]
        return q[q.cost_model==(model if model else r.cost_model)]
    def boot(q,part,block):
        a,z=[pd.Timestamp(v,tz='UTC') for v in f['periods'][part]]
        origin=a.normalize()-pd.Timedelta(days=a.weekday());n=int((z-pd.Timedelta(minutes=1)-origin).days//7)+1
        ix=((q.entry-origin).dt.total_seconds()//604800).astype(int)
        count=np.bincount(ix,minlength=n);value=np.bincount(ix,weights=q.net_return,minlength=n)
        rng=np.random.default_rng(20261006+block);starts=rng.integers(0,n,(10000,int(np.ceil(n/block))))
        draws=np.concatenate([((starts[:,j,None]+np.arange(block))%n) for j in range(starts.shape[1])],axis=1)[:,:n]
        den=count[draws].sum(1);num=value[draws].sum(1)
        return np.divide(num,den,out=np.full(10000,np.nan),where=den>0)
    rows=intervals=0
    def basic(q,r):
        assert len(q)==r.n and (q.reason=='stop').sum()==r.stop_count and (q.reason=='target').sum()==r.target_count
        assert np.isclose(q.net_return.mean(),r.mean,atol=1e-13,rtol=0)
        assert np.isclose((q.net_return>0).mean(),r.closed_win_rate,atol=1e-13,rtol=0)
    for r in pd.read_csv(o/'pooled_results.csv').itertuples():
        q=select(ledger,r);basic(q,r)
        for block in [1,4]:
            ci=np.nanquantile(boot(q,r.partition,block),[.025,.975]);saved=[getattr(r,f'block_{block}_{x}_R')*.02 for x in ['low','high']]
            assert np.allclose(ci,saved,atol=1e-12,rtol=0);intervals+=1
        rows+=1
    for r in pd.read_csv(o/'subgroups.csv').itertuples():
        q=select(ledger,r)
        for col in r.grouping.split('+'):q=q[q[col]==getattr(r,col)]
        basic(q,r);rows+=1
    for r in pd.read_csv(o/'contrasts.csv').itertuples():
        a=select(ledger,r,'research_all_exit_slip');b=select(ledger,r,'runtime_stop_fill')
        assert len(a)==len(b)==r.n
        for col in ['net_return','gross_return','fees','funding']:
            dest={'net_return':'net','gross_return':'gross'}.get(col,col)
            assert np.isclose(b[col].mean()-a[col].mean(),getattr(r,'difference_mean_'+dest),atol=1e-13,rtol=0)
        assert np.isclose(r.difference_mean_net,r.difference_mean_gross-r.difference_mean_fees-r.difference_mean_funding,atol=1e-13)
        for block in [1,4]:
            ci=np.nanquantile(boot(b,r.partition,block)-boot(a,r.partition,block),[.025,.975])
            saved=[getattr(r,f'difference_block_{block}_{x}_R')*.02 for x in ['low','high']]
            assert np.allclose(ci,saved,atol=1e-12,rtol=0);intervals+=1
        rows+=1
    for r in pd.read_csv(o/'stop_risk.csv').itertuples():
        q=select(ledger,r);stops=q[q.reason=='stop']
        assert len(q)==r.n and len(stops)==r.stops
        for expected,actual in [(stops.net_return.mean(),r.mean_stopped_net),(stops.net_return.min(),r.worst_stopped_net),(q.net_return.min(),r.worst_trade_net)]:assert np.isclose(expected,actual,atol=1e-13,rtol=0)
        rows+=1
    pairs=pd.read_csv(o/'paired_cost_changes.csv');assert len(pairs)==552
    assert (pairs.reason_old==pairs.reason_reconciled).all() and (pairs.exit_bar_old==pairs.exit_bar_reconciled).all()
    for r in pairs.itertuples():
        for col in ['gross_return','fees','funding','net_return']:
            assert np.isclose(getattr(r,col+'_reconciled')-getattr(r,col+'_old'),getattr(r,'delta_'+col),atol=1e-12,rtol=0)
    identity=pd.read_csv(o/'admission_identity.csv');assert len(identity)==48 and identity.identity_unchanged.all()
    assert ledger[ledger.cost_model=='runtime_stop_fill'].shape[0]==520 and raw.shape[0]==1104
    result=dict(status='pass',independent_scalar_cash_rows=scalar,report_rows_independently_rebuilt=rows,bootstrap_intervals_independently_rebuilt=intervals,
          paired_cost_rows_verified=len(pairs),admission_identity_rows=48,raw_rows=len(raw),ledger_rows=len(ledger),
          sources_inputs_references_runtime_outputs_verified=True,all_nonstop_rows_exactly_unchanged=True)
    (e/'REPORT_VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--cache',type=Path,required=True);p.add_argument('--runtime',type=Path,required=True);a=p.parse_args();verify(a.root,a.cache,a.runtime)
