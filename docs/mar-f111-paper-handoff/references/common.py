from pathlib import Path
import sys,json,hashlib,datetime as dt,itertools
ROOT=Path(__file__).resolve().parent
PRIOR=ROOT.parent/'mar_exit_sensitivity_20261009'
COHORT=ROOT.parent/'mar_volatility_cohort_20261009'
sys.path.insert(0,str(PRIOR))
import engine as legacy
import numpy as np
import pandas as pd
from numba import njit
from run_study import META
REF=legacy.REF;FEE=legacy.FEE;KEY=legacy.KEY
sha=legacy.sha;write=legacy.write

def recipes():
    activation=[('pct',v/100) for v in [.5,.75,1,1.25,1.5,1.75,2,2.5,3,4,5]]+[('R',v) for v in [.25,.5,.75,1,1.25,1.5,2]]+[('ATR',v) for v in [.5,.75,1,1.5,2,3]]
    subset=[('pct',v/100) for v in [1,1.5,2,3]]+[('R',v) for v in [.5,1]]+[('ATR',v) for v in [1,2]]
    gaps=[('pct',v/100) for v in [.25,.5,.75,1,1.5,2]]+[('ATR',v) for v in [.25,.5,.75,1,1.5]]+[('R',v) for v in [.25,.5,.75,1]]
    raw=[]
    for base in ['pct_s2_t2.5','atr_s3_t4']:
        for keep in [True,False]:
            def add(kind,tu='pct',tv=0,du='pct',dv=0,floor=0,partial=0):
                raw.append(dict(base=base,keep_target=keep,kind=kind,trigger_unit=tu,trigger_value=tv,distance_unit=du,distance_value=dv,floor_R=floor,partial_fraction=partial))
            add('none')
            for tu,tv in activation:
                for floor in [0,.25,.5]:add('breakeven' if floor==0 else 'floor',tu,tv,floor=floor)
            for tu,tv in subset:
                for du,dv in gaps:add('trail',tu,tv,du,dv)
                for partial in [.25,.5]:
                    add('partial_original',tu,tv,partial=partial)
                    add('partial_trail',tu,tv,'ATR',1,partial=partial)
    assert len(raw)==900
    unique={};aliases=[]
    for i,r in enumerate(raw):
        def canonical(unit,value):
            return (unit,value) if unit!='R' else ('pct',round(.02*value,12)) if r['base'].startswith('pct') else ('ATR',3*value)
        tu,tv=canonical(r['trigger_unit'],r['trigger_value']);du,dv=canonical(r['distance_unit'],r['distance_value'])
        key=(r['base'],r['keep_target'],r['kind'],tu,tv,du,dv,r['floor_R'],r['partial_fraction'])
        if key not in unique:
            unique[key]=r|dict(policy=len(unique),trigger_unit=tu,trigger_value=tv,distance_unit=du,distance_value=dv)
        aliases.append(r|dict(recipe=i,policy=unique[key]['policy']))
    policies=pd.DataFrame(unique.values());aliases=pd.DataFrame(aliases)
    return policies,aliases

def initialize():
    assert not (ROOT/'FREEZE.json').exists()
    src,ent,_=legacy.inputs();ent=ent[ent.entry_rule=='retest'].sort_values(['symbol','entry','signal_time','side']).reset_index(drop=True)
    assert len(ent)==530
    ent['eid']=np.arange(len(ent));ent['year']=ent.signal_time.dt.year;ent['high_vol']=ent.prior_atr/ent.close>=.01
    ent['population']=np.where(ent.symbol.isin(REF),'reference3','additional93');ent['sector']=np.where(ent.symbol.isin(REF),'BTC / ETH / SOL',ent.primary_sector)
    src['year']=src.signal_time.dt.year;src['high_vol']=src.prior_atr/src.close>=.01
    src['population']=np.where(src.symbol.isin(REF),'reference3','additional93');src['sector']=np.where(src.symbol.isin(REF),'BTC / ETH / SOL',src.primary_sector)
    ent.to_parquet(ROOT/'entries.parquet',index=False);src.to_parquet(ROOT/'sources.parquet',index=False)
    p,a=recipes();p.to_csv(ROOT/'policies.csv',index=False);a.to_csv(ROOT/'recipe_aliases.csv',index=False)
    write(ROOT/'FREEZE.json',dict(frozen_utc=dt.datetime.now(dt.timezone.utc).isoformat(),protocol_sha256=sha(ROOT/'PROTOCOL.md'),
        source_hashes={p.name:sha(p) for p in ROOT.glob('*.py')},input_hashes={str(p.relative_to(ROOT.parent)):sha(p) for p in [legacy.OLD/'results_v1/primary_trades.csv',PRIOR/'results/all_opportunities.parquet',PRIOR/'protection_results/all_opportunities.parquet']},
        nominal_recipes=len(a),unique_policies=len(p),retest_opportunities=len(ent),source_signals=len(src),new_outcomes_scored=False,reserved_2026_opened=False))
    print('FROZEN',len(p),'unique of',len(a),'recipes',flush=True)

def load():return pd.read_parquet(ROOT/'entries.parquet'),pd.read_parquet(ROOT/'sources.parquet'),pd.read_csv(ROOT/'policies.csv')
def params(p,atr,stop):
    trigger=p.trigger_value*(atr if p.trigger_unit=='ATR' else 1)
    distance=p.distance_value*(atr if p.distance_unit=='ATR' else 1)
    return trigger,distance,p.floor_R*stop

def admit_ids(g,e):
    # Entries already have a stable token/time/signal/side ordering.
    eids=g.eid.to_numpy(int);exitns=g.exit_ns.to_numpy(np.int64);order=np.argsort(eids);keep=[];occupied={};last_entry={}
    opposite=set(e.groupby(['symbol','entry']).side.nunique().loc[lambda x:x>1].index)
    for pos in order:
        row=e.loc[eids[pos]];symbol=row.symbol;t=row.entry.value
        if (symbol,row.entry) in opposite:continue
        if t>occupied.get(symbol,-1):keep.append(pos);occupied[symbol]=int(exitns[pos])
    return np.asarray(keep,int)

if __name__=='__main__':initialize()
