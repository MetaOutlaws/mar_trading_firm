from pathlib import Path
import sys,json,hashlib,itertools
ROOT=Path(__file__).resolve().parent;BASE=ROOT.parent
sys.path.insert(0,str(BASE/'mar_overnight_research_20261010'))
import run_stages12 as prior
from run_stages12 import inputs,admit,np,pd,FEE,bootstrap_weights
STRESSES=[0,5,10,20];POPS=['additional93','reference3','all96']
def save(d,n):
 d.to_parquet(ROOT/(n+'.parquet'),index=False,compression='zstd');d.to_csv(ROOT/(n+'.csv'),index=False)
def write(n,d): (ROOT/n).write_text(json.dumps(d,indent=2,default=str)+'\n')
def main():
 f=json.loads((ROOT/'FREEZE.json').read_text());assert hashlib.sha256((ROOT/'PROTOCOL.md').read_bytes()).hexdigest()==f['protocol_sha256']
 for p,h in f['source_sha256'].items():assert hashlib.sha256((BASE/p).read_bytes()).hexdigest()==h
 e,s=inputs();assert len(e)==530 and len(s)==1026
 for c in ['hourly_asof','feature_asof','btc_asof','crsi_asof']:assert (pd.to_datetime(s[c],utc=True)<=s.signal_time).all()
 assert (pd.to_datetime(s.regime_asof,utc=True)<s.signal_time).all()
 path=pd.read_parquet(BASE/'mar_protection_surface_20261010/results/opportunities.parquet',filters=[('policy','in',[284,331])]).merge(e[['eid','sid']],on='eid',validate='many_to_one')
 assert len(path)==2120 and not path.duplicated(['sid','policy','slippage']).any()
 books=[];decisions=[];cases=[]
 for c,x,p in itertools.product([0,1],repeat=3):
  case=f'F{c}{x}{p}';policy=331 if p else 284
  mask=(s.prior_atr/s.close>=.01)&((s.compression>.50) if c else True)&((s.extension_atr<=1) if x else True)
  cases.append(dict(case_id=case,compression_gate=c,extension_gate=x,late_floor=p,new_combination=case in ['F110','F101','F111']))
  for slip in [.002,.003]:
   g=path[(path.policy==policy)&(path.slippage==slip)&path.sid.isin(s.loc[mask,'sid'])].copy();g['case_id']=case;k,d=admit(g);books.append(k)
   q=s[['sid','symbol','signal_time','side','year','population','sector']].copy();q['case_id']=case;q['slippage']=slip;q['decision']='gate_filtered'
   q.loc[mask,'decision']='no_retest';q.loc[q.sid.isin(g.sid),'decision']='occupancy_rejected';q.loc[q.sid.isin(k.sid),'decision']='admitted';decisions.append(q)
 b=pd.concat(books,ignore_index=True);save(b,'books');save(pd.concat(decisions,ignore_index=True),'source_decisions');save(pd.DataFrame(cases),'case_registry')
 old=pd.concat([pd.read_parquet(BASE/'mar_overnight_research_20261010/interaction/books.parquet'),pd.read_parquet(BASE/'mar_overnight_research_20261010/regime/books.parquet').query("case_id=='R12'")]);checks=0
 for case,orig in {'F000':'I00','F010':'I10','F001':'I01','F011':'I11','F100':'R12'}.items():
  a=b[b.case_id==case];o=old[old.case_id==orig];z=a.merge(o,on=['sid','slippage'],suffixes=('_a','_o'),validate='one_to_one');assert len(z)==len(a)==len(o)
  for col in ['net_return','exit_ns','entry_i','exit_i','risk_scale']:assert np.allclose(z[col+'_a'],z[col+'_o'],atol=1e-12,rtol=0),col
  checks+=len(z)
 prior.summary(b,s,ROOT);prior.pairs(b,s,ROOT,'F000');other=ROOT/'versus_I11';other.mkdir();prior.pairs(b,s,other,'F011')
 allbooks=[];rows=[];conc=[];cal=[];cashchecks=0
 b['stop_drag_per_unit_slip']=np.where(b.reason.isin([1,4]),-(1-b.side*FEE)*b.exit_price/b.entry_price,0.)
 assert (b.partial_fraction==0).all();b.to_parquet(ROOT/'base_books.parquet',index=False)
 for bps in STRESSES:
  q=b.copy();delta=q.stop_drag_per_unit_slip*bps/10000
  q['extra_stop_bps']=bps;q['base_net_return']=q.net_return;q['exit_price']=np.where(q.reason.isin([1,4]),q.exit_price*(1-q.side*bps/10000),q.exit_price)
  q['gross_return']=q.side*(q.exit_price/q.entry_price-1);q['fees']=FEE*(1+q.exit_price/q.entry_price);q['net_return']=q.gross_return-q.fees-q.funding
  assert np.allclose(q.net_return,q.base_net_return+delta,atol=1e-12,rtol=0);cashchecks+=len(q);q['net_R']=q.net_return/q.stop_pct
  for y in [2022,2023,2024]:q[f'mark_{y}']+=np.where(q.exit_ns<pd.Timestamp(f'{y+1}-01-01',tz='UTC').value,delta,0.)
  allbooks.append(q)
  for (case,slip),g in q.groupby(['case_id','slippage']):
   for pop in POPS:
    z=g if pop=='all96' else g[g.population==pop];src=s if pop=='all96' else s[s.population==pop]
    for period,(lo,hi) in prior.PERIODS.items():
     zz=z[z.year.between(lo,hi)];v=zz.net_return*zz.risk_scale;den=int(src.year.between(lo,hi).sum())
     r=dict(case_id=case,slippage=slip,extra_stop_bps=bps,population=pop,period=period,trades=len(zz),original_signals=den,mean_R=zz.net_R.mean(),net_units=v.sum(),net_per_signal=v.sum()/den if den else np.nan)
     rows.append(r);tokens=v.groupby(zz.symbol).sum().sort_values(ascending=False);pos=tokens[tokens>0]
     conc.append(r|dict(without_top1=v.sum()-pos.head(1).sum(),without_top3=v.sum()-pos.head(3).sum(),without_top5=v.sum()-pos.head(5).sum(),top3=';'.join(pos.head(3).index)))
    prev=0
    for y in range(2022,2026):
     total=((z[f'mark_{y}'] if y<2025 else z.net_return)*z.risk_scale).sum();cal.append(dict(case_id=case,slippage=slip,extra_stop_bps=bps,population=pop,year=y,net_units=total-prev));prev=total
 stressed=pd.concat(allbooks,ignore_index=True);stressed.to_parquet(ROOT/'stressed_books.parquet',index=False)
 save(pd.DataFrame(rows),'stress_results');save(pd.DataFrame(conc),'stress_concentration');save(pd.DataFrame(cal),'stress_calendar')
 intervals=[];adjust=[];effects=[]
 for lo,hi in [(2022,2025),(2023,2025),(2025,2025)]:
  src=s[(s.population=='additional93')&s.year.between(lo,hi)]
  for block in [1,4]:
   weeks,w,ix=bootstrap_weights(src.signal_time,lo,hi,5000,block,20261010+lo+block);den=np.bincount(ix,minlength=len(weeks));bd=w@den;valid=bd>0
   for (slip,bps),g in stressed[(stressed.population=='additional93')&stressed.year.between(lo,hi)].groupby(['slippage','extra_stop_bps']):
    g=g.copy();g['week']=g.signal_time.dt.tz_localize(None).dt.to_period('W-SUN').dt.start_time;g['value']=g.net_return*g.risk_scale
    wide=g.pivot_table(index='week',columns='case_id',values='value',aggfunc='sum',fill_value=0).reindex(index=weeks,columns=sorted(b.case_id.unique()),fill_value=0).fillna(0)
    for control in ['F000','F011']:
     candidates=[x for x in wide.columns if x!=control];delta=wide[candidates].to_numpy()-wide[control].to_numpy()[:,None];obs=delta.sum(axis=0)/den.sum();boot=(w@delta)[valid]/bd[valid,None]
     for j,c in enumerate(candidates):
      low,high=np.quantile(boot[:,j],[.025,.975]);intervals.append(dict(case_id=c,control=control,slippage=slip,extra_stop_bps=bps,period=f'{lo}-{hi}',block_weeks=block,delta_per_signal=obs[j],low=low,high=high))
     if slip==.002 and bps==0 and control=='F000':
      centered=delta-den[:,None]*obs;maximum=((w@centered)[valid]/bd[valid,None]).max(axis=1);threshold=np.quantile(maximum,.95)
      for j,c in enumerate(candidates):adjust.append(dict(case_id=c,period=f'{lo}-{hi}',block_weeks=block,family_size=7,delta=obs[j],simultaneous95_lower=obs[j]-threshold,adjusted_p=(1+(maximum>=obs[j]).sum())/(1+len(maximum)),scope='this 7-alternative family only; prior search unadjusted'))
    if block==4:
     for name,terms in {'C_x_E_no_floor':{'F110':1,'F100':-1,'F010':-1,'F000':1},'C_x_P_no_extension':{'F101':1,'F100':-1,'F001':-1,'F000':1},'C_x_I11':{'F111':1,'F100':-1,'F011':-1,'F000':1}}.items():
      d=sum(wide[k]*v for k,v in terms.items()).to_numpy();bs=(w@d)[valid]/bd[valid];low,high=np.quantile(bs,[.025,.975]);effects.append(dict(effect=name,slippage=slip,extra_stop_bps=bps,period=f'{lo}-{hi}',total_units=d.sum(),per_signal=d.sum()/den.sum(),low=low,high=high))
 save(pd.DataFrame(intervals),'paired_intervals');save(pd.DataFrame(adjust),'search_adjustment');save(pd.DataFrame(effects),'factor_interactions')
 write('VERIFICATION.json',dict(status='pass',original_signals=len(s),entry_opportunities=len(e),source_decisions=len(pd.concat(decisions)),prior_book_rows_reconciled=checks,independent_cash_checks=cashchecks,base_books=16,stressed_books=64,source_asof_checks=5130,independent_admission_replay=True,execution_enabled=False,reserved_2026_opened=False))
 print(pd.DataFrame(rows).query("population=='additional93' and extra_stop_bps==0 and period in ['2022-25','2025']").to_string(index=False),flush=True)
if __name__=='__main__':main()
