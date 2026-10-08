"""Independent reconstruction of reported denominators, attribution and intervals."""
import argparse,json
import numpy as np
import pandas as pd
from run_retest import HERE,ROOT,PAIR,KEYS,PERIODS,sha,write,verified_reference

def close(a,b):
    assert np.isclose(a,b,atol=1e-12,rtol=1e-12,equal_nan=True),(a,b)

def intervals(p,part):
    a,z=PERIODS[part]
    weeks=pd.period_range(pd.Timestamp(a).to_period('W-SUN'),(pd.Timestamp(z)-pd.Timedelta(minutes=1)).to_period('W-SUN'),freq='W-SUN')
    w=pd.DatetimeIndex(p.signal_time).tz_localize(None).to_period('W-SUN')
    data=np.zeros((len(weeks),5))
    for k,week in enumerate(weeks):
        q=p.loc[w==week];ta=q[q.retest_admitted];ba=q[q.immediate_admitted]
        data[k]=[len(q),ta.net_return_retest.sum(),len(ta),ba.net_return_baseline.sum(),len(ba)]
    result={}
    for block in [1,4]:
        n=len(weeks);rng=np.random.default_rng(20261006+block)
        starts=rng.integers(0,n,(10000,int(np.ceil(n/block))))
        indices=np.concatenate([(starts[:,:,None]+offset)%n for offset in range(block)],axis=2).reshape(10000,-1)[:,:n]
        totals=data[indices].sum(axis=1)
        keep=totals[:,0]>0;sig=(totals[keep,1]-totals[keep,3])/totals[keep,0]
        for name,v in zip(['low','high'],np.quantile(sig,[.025,.975])):result[f'per_signal_block_{block}_{name}']=v
        result[f'per_signal_block_{block}_draws']=len(sig)
        keep=(totals[:,2]>0)&(totals[:,4]>0)
        trade=(totals[keep,1]/totals[keep,2]-totals[keep,3]/totals[keep,4])/.02
        if len(trade):
            for name,v in zip(['low','high'],np.quantile(trade,[.025,.975])):result[f'difference_block_{block}_{name}_R']=v
            result[f'difference_block_{block}_draws']=len(trade)
    return result

def verify(cache,runtime):
    out=HERE/'results_v1';f=json.loads((out/'freeze.json').read_text());s=json.loads((out/'status.json').read_text());assert s['status']=='complete'
    for group,root in [('sources',ROOT),('inputs',cache),('runtime_sources',runtime),('cached_references',ROOT)]:
        for n,h in f[group].items():assert sha(root/n)==h,n
    for n,h in s['output_hashes'].items():assert sha(out/n)==h,n
    _,ref,refledger=verified_reference(cache,runtime)
    raw=pd.read_parquet(out/'all_opportunities.parquet');ledger=pd.read_parquet(out/'pooled_ledger.parquet');plans=pd.read_parquet(out/'entry_plans.parquet')
    csv=lambda n:pd.read_csv(out/(n+'.csv'),float_precision='round_trip')
    pairs=csv('paired_raw_outcomes');pairs['signal_time']=pd.to_datetime(pairs.signal_time,utc=True)
    cols=[c for c in ref.columns if c!='arm']
    for frame,old in [(raw,ref),(ledger,refledger)]:
        q=frame[frame.entry_rule=='immediate']
        pd.testing.assert_frame_equal(q[cols].sort_values(PAIR).reset_index(drop=True),old[cols].sort_values(PAIR).reset_index(drop=True),check_exact=True)
    assert len(pairs)==276 and len(plans)==69
    for r in pairs.itertuples():
        ident=lambda d:(d.partition==r.partition)&(d.symbol==r.symbol)&(d.side==r.side)&(d.signal_i==r.signal_i)&(d.stress==r.stress)&(d.poll_minutes==r.poll_minutes)
        for arm,suffix,adcol in [('immediate','baseline','immediate_admitted'),('retest','retest','retest_admitted')]:
            a=raw[ident(raw)&(raw.entry_rule==arm)];b=ledger[ident(ledger)&(ledger.entry_rule==arm)]
            assert len(a)<=1 and len(b)<=1 and bool(len(b))==getattr(r,adcol)
            if len(a):
                for key in ['net_return','entry_price','exit_price','fees','funding','entry_i','exit_i']:close(getattr(r,key+'_'+suffix),a.iloc[0][key])
                assert getattr(r,'reason_'+suffix)==a.reason.iloc[0]
            else:assert arm=='retest' and r.entry_status!='filled' and np.isnan(r.net_return_retest)
        close(r.baseline_realized_net,r.net_return_baseline if r.immediate_admitted else 0)
        close(r.retest_realized_net,r.net_return_retest if r.retest_admitted else 0)
        close(r.delta_realized_net,r.retest_realized_net-r.baseline_realized_net)
        if r.entry_status=='filled':
            close(r.fill_price_improvement,r.side*(r.entry_price_baseline-r.entry_price_retest)/r.entry_price_baseline)
            assert 1<=r.entry_delay_minutes<=60
    tables={n:csv(n) for n in ['pooled_results','contrasts','admission_decomposition','missed_trades','matched_results','entry_timing']}
    checks=boot=0
    for r in tables['pooled_results'].itertuples():
        q=ledger[(ledger.entry_rule==r.entry_rule)&(ledger.poll_minutes==r.poll_minutes)&(ledger.stress==r.stress)&(ledger.partition==r.partition)]
        g=raw[(raw.entry_rule==r.entry_rule)&(raw.poll_minutes==r.poll_minutes)&(raw.stress==r.stress)&(raw.partition==r.partition)]
        n={'historical':45,'evaluation':15,'reserved_replication':9}[r.partition]
        assert r.raw_signals==n and r.qualified==len(g) and r.unfilled==n-len(g) and r.n==len(q) and r.rejected==len(g)-len(q)
        assert r.stop_count==int((q.reason=='stop').sum()) and r.target_count==int((q.reason=='target').sum()) and r.boundary_count==int((q.reason=='boundary_mtm').sum())
        close(r.mean,q.net_return.mean());close(r.net_per_original_signal,q.net_return.sum()/n);checks+=1
    for keys,p in pairs.groupby(['poll_minutes','partition','stress']):
        poll,part,stress=keys
        get=lambda name:tables[name][(tables[name].poll_minutes==poll)&(tables[name].partition==part)&(tables[name].stress==stress)]
        c=get('contrasts').iloc[0];a=p[p.immediate_admitted];b=p[p.retest_admitted]
        close(c.baseline_mean_net,a.net_return_baseline.mean());close(c.retest_mean_net,b.net_return_retest.mean());close(c.difference_mean_net,b.net_return_retest.mean()-a.net_return_baseline.mean())
        close(c.baseline_net_per_signal,a.net_return_baseline.sum()/len(p));close(c.retest_net_per_signal,b.net_return_retest.sum()/len(p));close(c.difference_net_per_signal,p.delta_realized_net.mean())
        for k,v in intervals(p,part).items():close(c[k],v);boot+=1
        d=get('admission_decomposition').iloc[0]
        shared=p[p.immediate_admitted&p.retest_admitted];new=p[~p.immediate_admitted&p.retest_admitted];removed=p[p.immediate_admitted&~p.retest_admitted]
        assert d.shared==len(shared) and d.newly_admitted==len(new) and d.removed==len(removed)
        close(d.shared_delta_net_sum,(shared.net_return_retest-shared.net_return_baseline).sum());close(d.new_net_sum,new.net_return_retest.sum());close(d.removed_baseline_net_sum,removed.net_return_baseline.sum());close(d.actual_difference_additive_sum,p.delta_realized_net.sum())
        for r in get('missed_trades').itertuples():
            q=a[a.no_trade_reason==r.no_trade_reason]
            assert r.n==len(q) and r.baseline_targets_missed==int((q.reason_baseline=='target').sum()) and r.baseline_stops_avoided==int((q.reason_baseline=='stop').sum())
            close(r.baseline_net_sum,q.net_return_baseline.sum());checks+=1
        m=get('matched_results').iloc[0]
        assert m.original_admitted==len(a) and m.qualified==int((a.entry_status=='filled').sum())
        close(m.retest_zero_fill_mean_net,a.net_return_retest.fillna(0).mean());close(m.difference_mean_net,(a.net_return_retest.fillna(0)-a.net_return_baseline).mean())
        for r in get('entry_timing').itertuples():
            q=p[p.entry_status=='filled'] if r.scope=='all_raw_fills' else b
            assert r.n==len(q) and r.better_fills==int((q.fill_price_improvement>0).sum()) and r.worse_fills==int((q.fill_price_improvement<0).sum())
            close(r.mean_delay_minutes,q.entry_delay_minutes.mean());close(r.mean_fill_price_improvement,q.fill_price_improvement.mean());checks+=1
        checks+=3
    decision=json.loads((out/'decision.json').read_text());gate={}
    for part in PERIODS:
        p=pairs[(pairs.partition==part)&(pairs.poll_minutes==1)&(pairs.stress==2)];b=p[p.retest_admitted]
        gate[part]=bool(len(b[b.reason_retest!='boundary_mtm'])>0 and b.net_return_retest.mean()>0 and p.delta_realized_net.mean()>0)
    assert decision['checks']==gate and decision['primary_continuation_screen_pass']==all(gate.values())
    v=dict(status='pass',paired_raw_rows_verified=len(pairs),baseline_rows_exact=len(ref),baseline_admitted_rows_exact=len(refledger),report_rows_checked=checks,bootstrap_values_independently_rebuilt=boot,source_input_runtime_reference_output_hashes_verified=True,decision_rebuilt=True)
    write(HERE/'REPORT_VERIFICATION.json',v);print(json.dumps(v,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cache',type=__import__('pathlib').Path,required=True);p.add_argument('--runtime',type=__import__('pathlib').Path,required=True);a=p.parse_args();verify(a.cache,a.runtime)
