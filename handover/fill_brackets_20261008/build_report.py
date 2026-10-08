"""Independent reporting, explicit paired-trade attribution, and living handover."""
import hashlib,json,shutil
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow as pa
pa.set_cpu_count(1);pa.set_io_thread_count(1)
W=Path(__file__).resolve().parent.parent;D=Path(__file__).resolve().parent
R=W/'three_token_work_20261007/research/isolated_token_study_20261003';E=R/'hourly_fill_brackets_20261008';O=E/'results_v1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
st=json.loads((O/'status.json').read_text());assert st['status']=='complete'
for n,h in st['output_hashes'].items():assert sha(O/n)==h,n
fr=json.loads((O/'freeze.json').read_text())
for group,root in [('sources',R),('inputs',W/'recovered_data'),('runtime_sources',W/'hourly_connors_runtime_20261008'),('cached_references',R)]:
 for n,h in fr[group].items():assert sha(root/n)==h,n
s=pd.read_csv(O/'pooled_results.csv');t=pd.read_parquet(O/'pooled_ledger.parquet',use_threads=False)
opp=pd.read_parquet(O/'all_opportunities.parquet',use_threads=False);sub=pd.read_csv(O/'subgroups.csv');contrasts=pd.read_csv(O/'contrasts.csv')
paired=pd.read_csv(O/'paired_raw_outcomes.csv');decomp=pd.read_csv(O/'admission_decomposition.csv');transitions=pd.read_csv(O/'outcome_transitions.csv')
periods=fr['periods'];checks=intervals=0

def boot(q,part,block):
 a,z=[pd.Timestamp(v,tz='UTC') for v in periods[part]];origin=a.normalize()-pd.Timedelta(days=a.weekday())
 n=int((z-pd.Timedelta(minutes=1)-origin).days//7)+1
 which=((q.entry-origin).dt.total_seconds()//604800).astype(int)
 count=np.bincount(which,minlength=n);value=np.bincount(which,weights=q.net_return,minlength=n)
 rng=np.random.default_rng(20261006+block);starts=rng.integers(0,n,(10000,int(np.ceil(n/block))))
 indices=np.concatenate([((starts[:,j,None]+np.arange(block))%n) for j in range(starts.shape[1])],axis=1)[:,:n]
 den=count[indices].sum(1);num=value[indices].sum(1)
 return np.divide(num,den,out=np.full(10000,np.nan),where=den>0)

for r in s.itertuples():
 q=t[(t.arm==r.arm)&(t.partition==r.partition)&(t.stress==r.stress)]
 assert len(q)==r.n and (q.reason=='stop').sum()==r.stop_count and (q.reason=='target').sum()==r.target_count
 assert np.isclose(q.net_return.mean(),r.mean,atol=1e-14) and np.isclose((q.net_return>0).mean(),r.closed_win_rate)
 assert not (q.reason=='boundary_mtm').any() and not q.ambiguous.any()
 for block in [1,4]:
  values=boot(q,r.partition,block);lo,hi=np.nanquantile(values,[.025,.975])
  assert np.allclose([lo,hi],.02*np.array([getattr(r,f'block_{block}_low_R'),getattr(r,f'block_{block}_high_R')]),atol=1e-12)
  intervals+=1
 checks+=1
for r in sub.itertuples():
 q=t[(t.arm==r.arm)&(t.partition==r.partition)&(t.stress==r.stress)]
 for col in r.grouping.split('+'):
  q=q[q.entry.dt.year==r.entry_year] if col=='entry_year' else q[q[col]==getattr(r,col)]
 assert len(q)==r.n and np.isclose(q.net_return.mean(),r.mean,atol=1e-14)
 assert (q.reason=='stop').sum()==r.stop_count and (q.reason=='target').sum()==r.target_count;checks+=1
for r in contrasts.itertuples():
 a=t[(t.arm=='quote_brackets')&(t.partition==r.partition)&(t.stress==r.stress)]
 b=t[(t.arm=='fill_brackets')&(t.partition==r.partition)&(t.stress==r.stress)]
 if r.view.startswith('counterfactual'):
  raw=opp[(opp.arm=='fill_brackets')&(opp.partition==r.partition)&(opp.stress==r.stress)]
  keys=['symbol','side','entry_i'];b=raw[pd.MultiIndex.from_frame(raw[keys]).isin(pd.MultiIndex.from_frame(a[keys]))]
 assert np.isclose(b.net_return.mean()-a.net_return.mean(),r.difference_mean_net,atol=1e-14)
 for block in [1,4]:
  x=boot(b,r.partition,block)-boot(a,r.partition,block);lo,hi=np.nanquantile(x,[.025,.975])
  assert np.allclose([lo,hi],.02*np.array([getattr(r,f'difference_block_{block}_low_R'),getattr(r,f'difference_block_{block}_high_R')]),atol=1e-12)
  intervals+=1
 checks+=1
for r in transitions.itertuples():
 q=paired[(paired.partition==r.partition)&(paired.stress==r.stress)]
 if r.scope=='original_admitted':q=q[q.baseline_admitted]
 q=q[(q.reason_quote==r.from_reason)&(q.reason_fill==r.to_reason)]
 assert len(q)==r.n and np.isclose(q.delta_net_return.sum(),r.difference_additive_sum,atol=1e-12);checks+=1
assert (decomp.newly_admitted==0).all() and (decomp.displaced==0).all()
assert len(t)==260 and t[['partition','symbol','side','entry_i']].drop_duplicates().shape[0]==65
for name,new in [('pooled_results.csv','results'),('contrasts.csv','contrasts'),('individual_trades.csv','individual_trades'),('outcome_transitions.csv','outcome_transitions')]:
 shutil.copyfile(O/name,D/f'MAR_fill_brackets_{new}_20261008.csv')
# User-facing paired export: distinguish timestamps from quote prices explicitly.
p=paired.rename(columns={'entry_quote':'entry_utc_quote_arm','entry_fill':'entry_utc_fill_arm','exit_bar_quote':'exit_utc_quote_arm','exit_bar_fill':'exit_utc_fill_arm','quote_quote':'exit_quote_price_quote_arm','quote_fill':'exit_quote_price_fill_arm'})
price=opp[opp.arm=='quote_brackets'][['partition','symbol','side','entry_i','stress','entry_quote']].rename(columns={'entry_quote':'entry_quote_price'})
p=p.merge(price,on=['partition','symbol','side','entry_i','stress'],validate='one_to_one')
p.to_csv(D/'MAR_fill_brackets_paired_outcomes_20261008.csv',index=False)
p[(p.stress==2)&p.baseline_admitted&(p.reason_quote!=p.reason_fill)].to_csv(D/'MAR_fill_brackets_changed_winners_20261008.csv',index=False)
pct=lambda x:f'{100*x:+.4f}%'
lines=[];base_lines=[]
for part,label in [('historical','2022–24'),('evaluation','2025'),('reserved_replication','2026 Jan–2 Oct')]:
 a=s[(s.partition==part)&(s.stress==2)&(s.arm=='quote_brackets')].iloc[0]
 b=s[(s.partition==part)&(s.stress==2)&(s.arm=='fill_brackets')].iloc[0]
 lines.append(f'| {label} | {int(b.n)} | {pct(a["mean"])} | {pct(b["mean"])} | {int(a.stop_count)} → {int(b.stop_count)} | {int(b.target_count)} | {100*b.closed_win_rate:.2f}% |')
 for cost in [1,2]:
  q=s[(s.partition==part)&(s.stress==cost)&(s.arm=='fill_brackets')].iloc[0]
  base_lines.append(f'| {label} | {"Base" if cost==1 else "Doubled slippage"} | {int(q.n)} | {int(q.stop_count)} | {int(q.target_count)} | {pct(q["mean"])} | {pct(q.block_4_low_R*.02)} to {pct(q.block_4_high_R*.02)} |')
summary='''## Latest completed: fill-price SL/TP audit, 8 October 2026

H-FILL-BRACKETS-01 is complete. Applying the approved2% stop/2.5% target to the
slipped fill changes outcomes materially. All three period means remain positive
at both costs, but historical stressed expectancy is thin. Paper already uses
fill-based levels; no runtime,approval,entry,stop/target percentage or mode changed.
Use the fill-origin results as the execution-aligned research reference going
forward. Preserve the earlier quote-origin results as their original model outputs.

| Period | Trades | Quote-origin net/trade | Fill-origin net/trade | Stops, old → new | Fill targets | Fill win rate |
|---|---:|---:|---:|---:|---:|---:|
'''+ '\n'.join(lines)+'''

Table uses doubled slippage,fees and funding. Five historical target winners and
one2025 target winner become stops. No stop becomes a target;2026 exit categories
are unchanged. No new or displaced admissions: the SAME65 trades are admitted in
both arms and both costs.260 ledger rows are overlapping scenario observations.
At base costs,three historical winners become stops and2025/2026 categories hold.

Historical ETH turns negative:17 trades,11 stops,mean−0.6246% stressed. BTC remains
+0.7929% over15 trades;SOL +0.1783% over9. Do not exclude ETH after observing this
result or retune entries to recover the old average. Historical pooled stressed
mean is+0.0702%,95% four-week interval−0.6258% to+0.6902%. The historical incremental
mean difference is−0.4301 percentage points; its four-week interval is−0.8978 to
−0.0207 percentage points. Bootstrap intervals condition on already examined data
and cannot establish future certainty or remove strategy-selection bias.

2025 fill-origin stressed mean+1.0412%,4 stops/15 trades;2026 +1.7240%,1 stop/9.
2026 had already been opened: this is execution sensitivity,not fresh validation.
The frozen positive-point robustness screen passes. Statistical equivalence,
full production parity and an independently established edge are NOT established.

Only bracket origin changed. Conservative research exit slippage on stops was
retained,although the runtime OHLC execution contract omits that second stop
slippage. Quote polling,actual spreads/fills,other strategies and live account
occupancy also remain distinct. No leverage/live change or cloud activation claim.

Protocol-before-scoring commit3b29ac2da5f20ff9e6b2850148a26958ef4c3a57.25 focused
tests passed;quote preflight reproduces138 raw and130 admitted cost rows. Full run:
276 independently checked minute paths,cost rows and runtime risk-level pairs;
12 independent admission replays;6 attribution reconciliations. All report tables
and48 bootstrap intervals were independently reconstructed. One successful run,
results_v1. Existing frozen research records remain unchanged.

ALSO FROZEN before any new-token outcomes: H-HOURLY-EXPANSION-01 in
hourly_expanded_replication_20261008/PROTOCOL.md. It adds this exact approved
hourly combination as a separate candidate beside the original6October all-clock
protocol. New-token primary uses fill-based brackets chosen BEFORE this audit's
outcomes;quote-origin comparison is diagnostic. Same pre-entry universe/liquidity
rules,strict BTC confirmation for each new token,conservative costs and provenance
gates. Both original95% and joint97.5% intervals are required as specified. No
new-token data or outcomes were inspected;the expanded runner is not yet implemented.

NEXT: separately audit scanner latency and sampled exit supervision against the
fill-origin benchmark,using actual cadence/log evidence where available and
clearly labelled minute-data proxies otherwise. Record the stop-exit slippage
convention separately. Then inspect winners and losses under this execution model
before proposing risk changes; the earlier19-stop/46-target count belongs to the
quote model. Current stressed fill model has25 stops/40 targets across65 trades.
Additional-token scoring follows its frozen protocol when audited data arrive.
No further experiment or background monitor has started in this turn.

See hourly_fill_brackets_20261008/FINDINGS.md,PROTOCOL.md and results_v1 in PR99.
Restore original MAR_hourly_compression_checkpoint_20261007.zip then
MAR_fill_brackets_checkpoint_20261008.zip;it includes all preceding increments.
Earlier sections below are historical and do not override this current status.
'''
more='''
## Fill-origin results and uncertainty

| Period | Costs | Trades | Stops | Targets | Mean net | Four-week95% interval |
|---|---|---:|---:|---:|---:|---|
'''+ '\n'.join(base_lines)+'''

Slipped entries shift BOTH barriers relative to the original market quote. That
can make a former target unreachable before a closer stop,even while surviving
target trades earn a slightly larger return relative to the fill. The six stressed
winner-to-stop conversions explain the weaker earlier-period means. The paired
trade file identifies every transition; it does not claim a new entry predictor.

The six changed stressed winners are ETH SHORT2022-06-11 09:00 UTC,ETH LONG
2023-11-24 08:00,ETH SHORT2024-12-08 09:00,SOL SHORT2024-05-23 11:00,SOL LONG
2024-07-26 14:00,and BTC LONG2025-04-25 12:00. All were admitted under both models.
Changed-winners export is six unique trades at stress2. Other changed paths with
the same exit category are retained in full paired outputs.

Raw opportunities are69 unique signals;65 admitted with4 token-busy rejections
per arm/cost across the periods. Forced original-entry and executable full replay
results happen to match because admission identities did not change. No terminal
marks or same-minute ambiguity occurred. No timeout was introduced.

Saved fractions0.001 mean0.1%;stress1 base/2 doubled slippage;side1 LONG/-1 SHORT;
timestamps UTC. The individual-trade file has numeric entry_quote; the original
paired research file's entry_quote/entry_fill fields are timestamp suffixes from
the two arms. The user-facing paired CSV explicitly renames these to entry_utc_*
and adds entry_quote_price to remove ambiguity. Quote is an exit quote in raw
execution records. Entry features must not be confused with later path outcomes.

The broader-token gate distinguishes positive point evidence from strong
confirmation. Insufficient trade support or incomplete provenance remains
inconclusive; it does not erase a positive measured mean.2026 additional-token
outcomes remain closed under the new protocol.
'''
(E/'FINDINGS.md').write_text('# H-FILL-BRACKETS-01 findings\n\n'+summary+more)
(D/'LATEST_STATUS.md').write_text('# MAR current research status,8 October2026\n\n'+summary)
for pth in [R/'RESEARCH_ROADMAP.md',R/'entry_quality_audit_20261006/HANDOVER.md',W/'hourly_mount_fix_20261007/START_HERE.md']:
 text=pth.read_text();head,rest=text.split('\n',1);pth.write_text(head+'\n\n'+summary+'\n'+rest.lstrip())
private=W/'regime_extension_handover_20261008/GROK_START_HERE.md';g=private.read_text();head,rest=g.split('\n',1)
g='# Grok private handover: execution audit and unchanged paper approval,8 October2026\n\n'+summary+'\n'+rest.lstrip()
private.write_text(g);(D/'GROK_START_HERE.md').write_text(g)
public='''# Grok: fill-price research audit and current paper rule,8 October2026

Approved PAPER strategy remains hourly_compression_btc_connors_loweff_v1:
BTC/ETH/SOL,both sides,1h,SL2%/TP2.5%,no timeout. Original compression + Connors +
BTC confirmation + one-ATR extension cap only when pre-signal ER24<0.30.
No runtime or approval change. Actual installation/scanning is not verified here.

Latest H-FILL-BRACKETS-01 audit aligns research bracket origin with the slipped
entry fill already used by runtime. Stressed mean returns:2022–24 +0.0702%
(41 trades,20 stops,21 targets);2025 +1.0412%(15,4,11);2026 +1.7240%(9,1,8).
Old quote-origin means were+0.5003%,+1.1993%,+1.5689% respectively. Five historical
winners and one2025 winner become stops;no admission identities change. Historical
ETH is negative. Positive pooled point results remain,but historical margin is thin
and uncertainty/earlier selection prevent a certainty claim. No retuning followed.

Read [PR99](https://github.com/MetaOutlaws/mar_trading_firm/pull/99),
research/isolated_token_study_20261003/hourly_fill_brackets_20261008/FINDINGS.md
and PROTOCOL.md.25 tests,276 paths/cost/risk-level checks,12 admissions,6 attributions,
and48 independently reconstructed intervals pass.260 rows are65 overlapping trades
under two arms/two costs. Prior evidence is preserved.2026 is already examined.

New-token protocol is frozen in hourly_expanded_replication_20261008/PROTOCOL.md.
It adds this exact hourly candidate alongside the preserved original all-clock
study;primary fill-origin brackets were chosen before this audit's results.
No new-token data were inspected and no new-token runner has been implemented.
Freeze and verify acquisition coverage and scoring code before opening outcomes.

Next research: scanner latency and sampled exits,separately from the stop-exit
slippage convention. Use real operational evidence when available;minute-data
proxies do not establish full production parity. Winner/loss diagnosis should use
the fill-origin results (25 stops/40 targets),not only the old quote-based ledger.

Runtime [PR101](https://github.com/MetaOutlaws/mar_trading_firm/pull/101) and its
reviewed HOURLY_LOWEFF_APPROVAL.md remain the operational source. Publication is
not proof of scanning. No new symbol,live/leverage or duplicate strategy approval.
The complete operational instructions remain in the owner's private checkpoint.

Recovery:original MAR_hourly_compression_checkpoint_20261007.zip followed by
MAR_fill_brackets_checkpoint_20261008.zip;raw inputs separate. Current checkpoint
preserves all previous increments. No background test/monitor is running.
'''
(D/'PUBLIC_GROK_START_HERE.md').write_text(public)
for pth in [W/'three_token_work_20261007/GROK_START_HERE.md',W/'hourly_connors_runtime_20261008/GROK_START_HERE.md']:pth.write_text(public)
verification=dict(status='pass',report_rows_checked=checks,bootstrap_intervals_independently_rebuilt=intervals,unique_admitted_trades=65,overlapping_scenario_rows=260,attribution_checks=6,all_frozen_hashes_verified=True,prior_results_preserved=True)
(D/'REPORT_VERIFICATION.json').write_text(json.dumps(verification,indent=2)+'\n');print(json.dumps(verification));print(summary)
