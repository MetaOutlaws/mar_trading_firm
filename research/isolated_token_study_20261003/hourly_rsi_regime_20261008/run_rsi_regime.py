"""Four fixed RSI policies on the approved BTC+Connors+conditional-cap benchmark."""
import argparse, datetime as dt, json, platform, sys
from pathlib import Path
import numpy as np
import pandas as pd
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT/'hourly_extension_filter_20261007'))
from run_extension import admit, replay, sha, write, load, report_metrics, score, contrast, reconcile, KEYS, STOP, TARGET, PERIODS, SYMBOLS
sys.path.insert(0, str(ROOT/'hourly_extension_regime_20261008'))
from regime_rule import context as regime_context, independent_at
from rsi_regime_rule import policy_pass, POLICIES
from rsi_rule import hourly_context, independent_context, context_at, gate
PRIOR = ROOT/'hourly_extension_regime_20261008/results_v1'
RSI = ROOT/'hourly_rsi_filter_20261008/results_v1'
ARMS = tuple('approved_'+p for p in POLICIES)


def freeze(cache, out, commit):
    out.mkdir(parents=True, exist_ok=False)
    refs = {}
    for prior in [PRIOR, RSI]:
        status = json.loads((prior/'status.json').read_text())
        assert status['status'] == 'complete'
        f = json.loads((prior/'freeze.json').read_text())
        for group, root in [('sources', ROOT), ('inputs', cache), ('features', ROOT)]:
            for n, h in f[group].items(): assert sha(root/n) == h, n
        for n, h in status['output_hashes'].items(): assert sha(prior/n) == h, n
        for n in ['status.json', 'freeze.json', 'all_opportunities.parquet', 'pooled_ledger.parquet', 'VERIFICATION.json']:
            refs[str((prior/n).relative_to(ROOT))] = sha(prior/n)
    refs[str((PRIOR/'hourly_state_frequency.csv').relative_to(ROOT))] = sha(PRIOR/'hourly_state_frequency.csv')
    approval = ROOT/'hourly_extension_regime_20261008/OWNER_APPROVAL.md'
    refs[str(approval.relative_to(ROOT))] = sha(approval)
    sources = {str(p.relative_to(ROOT)): sha(p) for p in ROOT.rglob('*.py')}
    for name in ['PROTOCOL.md', 'NOVELTY_AUDIT.md']:
        sources[str((HERE/name).relative_to(ROOT))] = sha(HERE/name)
    write(out/'freeze.json', dict(frozen_at=dt.datetime.now(dt.timezone.utc).isoformat(), protocol_commit=commit,
        sources=sources, inputs=f['inputs'], features=f['features'], cached_references=refs,
        arms=ARMS, benchmark='combo_loweff', rsi_period=14, long_ceiling=70, short_floor=30,
        efficiency_cutoff=.30, extension_cap_atr=1., stop=STOP, target=TARGET, scores_2026=False,
        packages=dict(python=platform.python_version(), numpy=np.__version__, pandas=pd.__version__)))
    print('FROZEN', out, flush=True)


def run(cache, out):
    f = json.loads((out/'freeze.json').read_text())
    for kind, root in [('inputs', cache), ('sources', ROOT), ('features', ROOT), ('cached_references', ROOT)]:
        for n, h in f[kind].items(): assert sha(root/n) == h, n
    assert not (out/'status.json').exists(), 'Preserve attempts; use a new output folder'
    write(out/'status.json', dict(status='running', started_at=dt.datetime.now(dt.timezone.utc).isoformat()))
    old_opp = pd.read_parquet(PRIOR/'all_opportunities.parquet')
    raw = old_opp[old_opp.arm == 'original_none'].copy()
    old_rsi = pd.read_parquet(RSI/'all_opportunities.parquet').query('arm == "baseline"')
    assert reconcile(raw, old_rsi) == 286
    assert len(raw) == 286 and not raw.duplicated(KEYS+['stress']).any()
    contexts = []
    for symbol in SYMBOLS:
        c, _ = load(cache, symbol)
        q = hourly_context(c)
        ref = independent_context(c)
        er = regime_context(c.close.resample('h', closed='left', label='right').last())
        selected = raw[(raw.symbol == symbol) & (raw.stress == 1)]
        original = old_rsi[(old_rsi.symbol == symbol) & (old_rsi.stress == 1)].set_index(['side','entry_i'])
        for row in selected.itertuples():
            T = row.entry
            x = context_at(q, [T]).iloc[0]
            y = ref.loc[T]
            for col in ['filter_rsi14', 'avg_gain', 'avg_loss']:
                assert np.isclose(x[col], y[col], atol=1e-9, rtol=1e-11), (symbol, T, col)
                assert np.isclose(x[col], original.loc[(row.side,row.entry_i), col], atol=1e-9, rtol=1e-11)
            assert np.isclose(x.filter_rsi14, row.entry_rsi14, atol=1e-9, rtol=1e-11)
            state = er.loc[T]
            assert np.isclose(state.efficiency24_before_signal, independent_at(c,T), atol=1e-12)
            assert np.isclose(state.efficiency24_before_signal, row.efficiency24_before_signal, atol=1e-12)
            assert state.directional == row.directional and state.regime_asof == row.regime_asof == T-pd.Timedelta(hours=1)
            assert x.rsi_asof == T and x.rsi_last_minute == T-pd.Timedelta(minutes=1)
            contexts.append({k:getattr(row,k) for k in KEYS} | x.to_dict())
        print('INDEPENDENT_RSI_AND_STATE_VERIFIED', symbol, len(selected), flush=True)
    ctx = pd.DataFrame(contexts)
    assert len(ctx) == 143 and not ctx.duplicated(KEYS).any()
    ctx.to_csv(out/'rsi_regime_context.csv', index=False)
    raw = raw.merge(ctx, on=KEYS, validate='many_to_one')
    raw['passes_rsi'] = gate(raw.filter_rsi14, raw.side)
    raw['passes_approved'] = raw.passes_both & (raw.directional | raw.passes_extension)
    raw.to_csv(out/'raw_signal_outcomes.csv', index=False)
    approved = raw[raw.passes_approved]
    approved_opp_count = reconcile(approved, old_opp[old_opp.arm == 'combo_loweff'])
    opp = pd.concat([approved[policy_pass(approved.filter_rsi14, approved.side, approved.efficiency24_before_signal, p)].assign(arm='approved_'+p)
                     for p in POLICIES], ignore_index=True)
    opp.to_parquet(out/'all_opportunities.parquet', index=False)
    ledgers=[]; rejections=[]; summaries=[]; subgroups=[]; annual=[]; leaveouts=[]
    for arm in ARMS:
        for part, (a,z) in PERIODS.items():
            for stress in [1,2]:
                g=opp[(opp.arm==arm)&(opp.partition==part)&(opp.stress==stress)]
                t,rej=admit(g); ids,counts=replay(g)
                assert ids==list(t[['symbol','tf','side','entry_i']].itertuples(index=False,name=None))
                assert counts==(rej.reason.value_counts().to_dict() if len(rej) else {}) and len(t)+len(rej)==len(g)
                meta=dict(arm=arm,partition=part,stress=stress)
                ledgers.append(t)
                if len(rej): rejections.append(rej.assign(**meta))
                summaries.append(meta|dict(opportunities=len(g),rejected=len(rej))|report_metrics(t,STOP,a,z))
                for year,y in t.groupby(t.entry.dt.year): annual.append(meta|dict(entry_year=int(year))|score(y,STOP))
                for grouping in [['symbol'],['side'],['directional'],['symbol','side']]:
                    for keys,y in t.groupby(grouping):
                        keys=keys if isinstance(keys,tuple) else (keys,)
                        subgroups.append(meta|dict(grouping='+'.join(grouping))|dict(zip(grouping,keys))|score(y,STOP))
                for symbol in SYMBOLS:
                    q=t[t.symbol!=symbol]
                    leaveouts.append(meta|dict(excluded_symbol=symbol,n=len(q),mean_net=q.net_return.mean(),method='remove from admitted ledger; no replacement replay'))
        print('ADMISSIONS_REPLAYED',arm,flush=True)
    ledger=pd.concat(ledgers,ignore_index=True)
    old=pd.read_parquet(PRIOR/'pooled_ledger.parquet')
    reconciled=reconcile(ledger[ledger.arm=='approved_none'],old[old.arm=='combo_loweff'])
    assert reconciled==112
    assert ledger.exit_bar.max()<pd.Timestamp('2026-01-01',tz='UTC')
    assert (ledger.regime_asof<ledger.entry).all() and (ledger.rsi_last_minute<ledger.entry).all() and (ledger.rsi_asof==ledger.entry).all()
    assert np.allclose(ledger.net_return,ledger.quoted_return-ledger.slippage_drag-ledger.fees-ledger.funding,atol=1e-12,rtol=0)
    for _,g in ledger.groupby(['arm','partition','stress','symbol']):
        g=g.sort_values('entry');assert (g.entry.to_numpy()[1:]>g.exit_bar.to_numpy()[:-1]).all()
    ledger.to_parquet(out/'pooled_ledger.parquet',index=False)
    ledger.to_csv(out/'individual_trades.csv',index=False)
    summary=pd.DataFrame(summaries); summary.to_csv(out/'pooled_results.csv',index=False)
    for n,x in [('subgroups',subgroups),('annual_by_entry_year',annual),('leave_one_token_out',leaveouts)]: pd.DataFrame(x).to_csv(out/f'{n}.csv',index=False)
    (pd.concat(rejections,ignore_index=True) if rejections else pd.DataFrame(columns=['arm','partition','stress','reason'])).to_csv(out/'rejections.csv',index=False)
    contrasts=[]; changes=[]; decomp=[]; state_effects=[]; exclusions=[]
    for (part,stress),g in ledger.groupby(['partition','stress']):
        b=g[g.arm=='approved_none']; bi=pd.MultiIndex.from_frame(b[KEYS])
        for policy in POLICIES[1:]:
            t=g[g.arm=='approved_'+policy]; ti=pd.MultiIndex.from_frame(t[KEYS])
            meta=dict(partition=part,stress=int(stress),treatment='approved_'+policy,comparator='approved_none')
            contrasts.append(meta|dict(difference_mean_net=t.net_return.mean()-b.net_return.mean())|contrast(t,b,*PERIODS[part]))
            left=b[~bi.isin(ti)]; new=t[~ti.isin(bi)]; shared=t[ti.isin(bi)];reconcile(shared,b[bi.isin(ti)])
            left_pass=policy_pass(left.filter_rsi14,left.side,left.efficiency24_before_signal,policy)
            direct=left[~left_pass]; occupied=left[left_pass]
            delta=t.net_return.sum()-b.net_return.sum()
            assert np.isclose(delta,new.net_return.sum()-direct.net_return.sum()-occupied.net_return.sum(),atol=1e-12)
            row=meta|dict(shared=len(shared),direct_exclusions=len(direct),lost_through_occupancy=len(occupied),newly_admitted=len(new),difference_additive_net_sum=delta)
            for label,q in [('retained',shared),('excluded_by_policy',direct),('lost_to_changed_occupancy',occupied),('newly_admitted',new)]:
                changes.append(q.assign(treatment='approved_'+policy,comparator='approved_none',admission_status=label))
                row[label+'_stops']=int((q.reason=='stop').sum()); row[label+'_targets']=int((q.reason=='target').sum());row[label+'_net_sum']=q.net_return.sum()
            decomp.append(row)
            for scope,full in [('approved_raw',approved[(approved.partition==part)&(approved.stress==stress)]),('benchmark_admitted',b)]:
                dropped=full[~policy_pass(full.filter_rsi14,full.side,full.efficiency24_before_signal,policy)]
                exclusions.append(meta|dict(scope=scope,n=len(full),removed_n=len(dropped),removed_stops=int((dropped.reason=='stop').sum()),removed_targets=int((dropped.reason=='target').sum()),removed_mean=dropped.net_return.mean()))
        for state,q in b.groupby('directional'):
            kept=q[q.passes_rsi];removed=q[~q.passes_rsi]
            state_effects.append(dict(partition=part,stress=int(stress),directional=bool(state),n=len(q),baseline_mean=q.net_return.mean(),retained_n=len(kept),retained_mean=kept.net_return.mean(),removed_n=len(removed),removed_stops=int((removed.reason=='stop').sum()),removed_targets=int((removed.reason=='target').sum()),removed_mean=removed.net_return.mean(),method='diagnostic benchmark subset; not a new admission replay'))
    contrasts=pd.DataFrame(contrasts);contrasts.to_csv(out/'contrasts.csv',index=False)
    pd.DataFrame(decomp).to_csv(out/'admission_decomposition.csv',index=False)
    pd.concat(changes,ignore_index=True).to_csv(out/'admission_changes.csv',index=False)
    pd.DataFrame(state_effects).to_csv(out/'state_effects.csv',index=False)
    pd.DataFrame(exclusions).to_csv(out/'exclusion_summary.csv',index=False)
    checks={}
    for policy in POLICIES[1:]:
        for stress in [1,2]:
            q=contrasts[(contrasts.treatment=='approved_'+policy)&(contrasts.stress==stress)]
            t=summary[(summary.arm=='approved_'+policy)&(summary.stress==stress)]
            checks[f'{policy}_cost{stress}']=bool(len(q)==2 and len(t)==2 and (t.n>0).all() and (t['mean']>0).all() and (q.difference_mean_net>=-1e-12).all() and (q.difference_mean_net>1e-12).any())
    write(out/'decision.json',dict(point_screen_by_policy={p:all(checks[f'{p}_cost{x}'] for x in [1,2]) for p in POLICIES[1:]},checks=checks,independent_edge_established=False,statistical_noninferiority_established=False,automatic_deployment=False,scores_2026=False))
    write(out/'VERIFICATION.json',dict(status='pass',independent_rsi_contexts=143,independent_regime_contexts=143,cached_raw_cost_rows_reconciled=286,prior_approved_opportunity_cost_rows_reconciled=approved_opp_count,prior_approved_admitted_cost_rows_reconciled=reconciled,independent_admission_runs=16,attribution_checks=12,ledger_rows=len(ledger),new_minute_paths_simulated=0,scores_2026=False))
    write(out/'status.json',dict(status='complete',completed_at=dt.datetime.now(dt.timezone.utc).isoformat(),output_hashes={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='status.json'}))
    print(summary[['arm','partition','stress','n','mean','stop_count','target_count']].to_string(index=False),flush=True)
    print(json.dumps(checks),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['freeze','run']);p.add_argument('--cache',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--protocol-commit');a=p.parse_args()
    if a.command=='freeze':
        assert a.protocol_commit and len(a.protocol_commit)==40
        freeze(a.cache,a.out,a.protocol_commit)
    else:run(a.cache,a.out)
