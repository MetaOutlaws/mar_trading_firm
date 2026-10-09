"""Report and independently verify frozen results without additional strategy scoring."""
import hashlib,json,shutil
from pathlib import Path
import numpy as np
import pandas as pd
W=Path(__file__).resolve().parent.parent;D=Path(__file__).resolve().parent
R=W/'three_token_work_20261007/research/isolated_token_study_20261003';E=R/'hourly_reserved_2026_20261008';O=E/'results_v1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
status=json.loads((O/'status.json').read_text());assert status['status']=='complete'
for n,h in status['output_hashes'].items():assert sha(O/n)==h,n
s=pd.read_csv(O/'pooled_results.csv');t=pd.read_parquet(O/'pooled_ledger.parquet')
sub=pd.read_csv(O/'subgroups.csv');f=json.loads((O/'freeze.json').read_text())
for group,root in [('sources',R),('inputs',W/'recovered_data'),('runtime_sources',W/'hourly_connors_runtime_20261008')]:
 for n,h in f[group].items():assert sha(root/n)==h,n
assert not t.duplicated(['symbol','side','entry','stress']).any()
checks=0
for r in s.itertuples():
 q=t[t.stress==r.stress];assert len(q)==r.n==9
 assert (q.reason=='stop').sum()==r.stop_count==1 and (q.reason=='target').sum()==r.target_count==8
 assert np.isclose(q.net_return.mean(),r.mean,atol=1e-14)
 assert np.isclose((q.net_return>0).mean(),r.win_rate,atol=1e-14)
 assert np.isclose(q.loc[q.net_return>0,'net_return'].sum()/-q.loc[q.net_return<0,'net_return'].sum(),r.pf,atol=1e-12)
 assert not q.ambiguous.any() and not (q.reason=='boundary_mtm').any()
 # Independent weekly-array construction; same registered circular sampling seeds.
 a=pd.Timestamp('2026-01-01',tz='UTC');z=pd.Timestamp('2026-10-02 16:00',tz='UTC')
 origin=a.normalize()-pd.Timedelta(days=a.weekday());n=int((z-pd.Timedelta(minutes=1)-origin).days//7)+1
 week=((q.entry-origin).dt.total_seconds()//604800).astype(int)
 counts=np.bincount(week,minlength=n);sums=np.bincount(week,weights=q.net_return,minlength=n)
 for block in [1,4]:
  rng=np.random.default_rng(20261006+block);starts=rng.integers(0,n,(10000,int(np.ceil(n/block))))
  samples=[]
  for draw in starts:
   indices=np.concatenate([(j+np.arange(block))%n for j in draw])[:n]
   count=counts[indices].sum()
   if count:samples.append(sums[indices].sum()/count)
  lo,hi=np.quantile(samples,[.025,.975]);assert len(samples)==getattr(r,f'block_{block}_draws')
  assert np.allclose([lo,hi],np.array([getattr(r,f'block_{block}_low_R'),getattr(r,f'block_{block}_high_R')])*.02,atol=1e-12)
 checks+=1
for r in sub.itertuples():
 q=t[t.stress==r.stress]
 for field in r.grouping.split('+'):
  if field=='month':q=q[q.entry.dt.strftime('%Y-%m')==r.month]
  else:q=q[q[field]==getattr(r,field)]
 assert len(q)==r.n and np.isclose(q.net_return.mean(),r.mean,atol=1e-14)
 assert (q.reason=='stop').sum()==r.stop_count and (q.reason=='target').sum()==r.target_count
 checks+=1
old=pd.read_csv(R/'hourly_extension_regime_20261008/results_v1/pooled_results.csv').query('arm=="combo_loweff"').copy()
comparison=pd.concat([old,s],ignore_index=True)
comparison['comparison_scope']='Descriptive periods; different durations and selected/reused history, not a treatment contrast.'
comparison.to_csv(D/'MAR_2026_replication_period_comparison_20261008.csv',index=False)
shutil.copyfile(O/'individual_trades.csv',D/'MAR_2026_replication_individual_trades_20261008.csv')
shutil.copyfile(O/'pooled_results.csv',D/'MAR_2026_replication_results_20261008.csv')
shutil.copyfile(O/'subgroups.csv',D/'MAR_2026_replication_subgroups_20261008.csv')
stress=s[s.stress==2].iloc[0];base=s[s.stress==1].iloc[0]
pct=lambda x:f'{100*x:+.4f}%'
rows=[]
for label,part,frame in [('2022–24','historical',old),('2025','evaluation',old),('2026 reserved interval','reserved_replication',s)]:
 x=frame[(frame.partition==part)&(frame.stress==2)].iloc[0]
 rows.append(f'| {label} | {int(x.n)} | {int(x.stop_count)} | {int(x.target_count)} | {100*x.closed_win_rate:.2f}% | {pct(x["mean"])} |')
tokenrows=[]
for x in sub[(sub.stress==2)&(sub.grouping=='symbol')].itertuples():
 tokenrows.append(f'| {x.symbol} | {x.n} | {x.stop_count} | {x.target_count} | {pct(x.mean)} |')
summary='''## Latest completed: fixed-strategy 2026 replication, 8 October 2026

H-2026-REPLICATION-01 is complete. The approved PAPER rule remains
`hourly_compression_btc_connors_loweff_v1`: hourly compression + BTC confirmation
+ Connors + a one-ATR extension cap only when prior ER24<0.30; BTC/ETH/SOL,
LONG+SHORT, SL2%, TP2.5%, no timeout. No runtime/approval change was made.

**Positive point replication:** 9 trades, 8 targets, 1 stop-out (11.11%), 88.89%
closed win rate. Mean net return is +1.7240% at base costs and +1.5689% at doubled
slippage. No boundary marks, ambiguous exits or admission rejections. Nine trades
across seven entry dates/seven calendar weeks; 18 exported rows are the SAME nine
trades under two cost assumptions, not 18 independent observations.

| Period | Trades | Stops | Targets | Win rate | Stressed mean net/trade |
|---|---:|---:|---:|---:|---:|
'''+ '\n'.join(rows)+'''

Interval: 1 January 2026 00:00 UTC through 2 October 2026 16:00 UTC exclusive.
Last eight candle hours omitted based on funding coverage before scoring. No
carry-in positions; pre-2026 data used only as causal warm-up for this replay.

This is a **temporal replication, not an untouched holdout**: original PR92 exposed
full-span future-path opportunity summaries including 2026, and external Grok use
is unknown. The current sequence had no saved 2026 strategy trades before this
run. Raw funding provenance remains provisional; it matches the approved sequence.

Stressed 95% bootstrap intervals for the mean: one-week blocks '''+pct(stress.block_1_low_R*.02)+' to '+pct(stress.block_1_high_R*.02)+''';
four-week blocks '''+pct(stress.block_4_low_R*.02)+' to '+pct(stress.block_4_high_R*.02)+'''. The latter includes zero.
Both point means are positive; the predeclared stronger interval check does not
pass. This supports continued paper evaluation, not certainty or leverage readiness.

Protocol-before-scoring commit `988bb74b17854704c7fc4094f5577619d017726c`.
Historical preflight reproduced all120 approved opportunity cost rows and112
admitted cost rows (56 trades). New run verified30 independent entry contexts,
six runtime signal frames/39,552 hour-side decisions,30 trailing850-hour decisions,
all9 minute barrier paths,18 independent cost calculations and two admissions.
Four bootstrap intervals were independently reconstructed. One successful 2026
run, results_v1; initial historical-only adapter failure is preserved separately.

NEXT: verify actual paper installation/scanning and compare subsequent signal/fill
logs with the frozen rule; collect forward observations without tuning on them.
Use the preregistered broader-token replication when additional data arrive.
2026 has now been opened: any further optimisation on it is exploratory. No new
filter sweep, live/leverage change or background monitor was started. Cloud
activation is still unverified here; GitHub publication is not operational proof.

Read hourly_reserved_2026_20261008/FINDINGS.md and PROTOCOL.md in PR99. Restore the
original hourly base then MAR_2026_replication_checkpoint_20261008.zip; this increment
includes preceding increments. Older notes below describe historical work and do
not override this current status.
'''
findings='# H-2026-REPLICATION-01 findings\n\n'+summary+'''
## Token detail, doubled slippage

| Token | Trades | Stops | Targets | Mean net/trade |
|---|---:|---:|---:|---:|
'''+ '\n'.join(tokenrows)+'''

SOL supplies five of nine trades and about70.4% of positive token net-return sums;
ETH has only one observation. Removing each token from the admitted ledger keeps
the remaining stressed mean positive; this is descriptive, without replacement.
LONG:5 trades/1 stop/4 targets, +1.1906% mean. SHORT:4 trades/0 stops/4 targets,
+2.0418% mean. Do not interpret tiny token/side cells as selection rules.

The sole stop is BTC LONG, entry2026-07-10 02:00 UTC, exit2026-07-13 05:00 UTC,
stressed net−2.3663%, about75.02h held. This documents the loss; no recovery or
exit optimisation was run. Median hold16.22h; longest75.02h. Stressed profit
factor6.97 is a nine-trade estimate. Net percentages are per-trade returns under
the research model; their additive sum is not a compounded account return.

Thirty original compression entry contexts were examined causally; nine passed
all approved filters. Only those nine were scored. No 2026 counterfactual arms,
RSI policies or alternate stops were calculated, and no winners-sacrificed contrast
is claimed. Historical and2025 positive outcomes remain intact but are selected
or reused evidence. No year was labelled categorically trending/choppy here.

Saved CSVs contain base stress=1 and doubled-slippage stress=2; values are fractions
(0.015689 means1.5689%), side1 LONG/-1 SHORT, timestamps UTC. Entry contexts are
known at entry; exit/path/cost columns are later outcomes and cannot be predictors.
Production sampled quotes, fill-relative brackets and shared-account occupancy
differ from the research simulator; entry parity is not realised-PnL parity.
'''
(E/'FINDINGS.md').write_text(findings);(D/'LATEST_STATUS.md').write_text('# MAR current status, 8 October 2026\n\n'+summary)
for p in [R/'RESEARCH_ROADMAP.md',R/'entry_quality_audit_20261006/HANDOVER.md',W/'hourly_mount_fix_20261007/START_HERE.md']:
 text=p.read_text();head,rest=text.split('\n',1);p.write_text(head+'\n\n'+summary+'\n'+rest.lstrip())
gp=W/'regime_extension_handover_20261008/GROK_START_HERE.md';g=gp.read_text()
g=g.replace('# Grok handover — current approval and completed RSI regime study, 8 October 2026','# Grok handover — current approval and completed 2026 replication, 8 October 2026')
g=g.replace('No2026 outcomes scored. Runtime rule, installer and approval are unchanged.','That RSI experiment scored no2026 outcomes. Runtime rule, installer and approval are unchanged.')
g=g[:g.index('Next research is independent confirmation,')]+summary+'\n'
for p in [gp,D/'GROK_START_HERE.md',W/'three_token_work_20261007/GROK_START_HERE.md',W/'hourly_connors_runtime_20261008/GROK_START_HERE.md']:p.write_text(g)
verification=dict(status='pass',report_rows_checked=checks,independent_bootstrap_intervals=4,unique_trades=9,cost_rows=18,frozen_input_and_source_hashes_verified=True,earlier_results_unmodified=True)
(D/'REPORT_VERIFICATION.json').write_text(json.dumps(verification,indent=2)+'\n');print(json.dumps(verification));print(summary)
