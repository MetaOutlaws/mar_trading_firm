"""Coverage and prior-entry-date inventory only; never reads trade returns."""
import argparse, json, hashlib
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
SYMBOLS=('BTCUSDT','ETHUSDT','SOLUSDT')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def audit(cache):
    records=[];inputs={};inventory=[]
    for s in SYMBOLS:
        cp=cache/f'{s}_1m.parquet';fp=cache/'funding'/f'{s}_funding.parquet'
        c=pd.read_parquet(cp);f=pd.read_parquet(fp)
        assert isinstance(c.index,pd.DatetimeIndex) and isinstance(f.index,pd.DatetimeIndex)
        assert c.index.equals(pd.date_range('2022-01-01','2026-10-03',freq='min',inclusive='left',tz='UTC',name=c.index.name))
        assert f.index.is_unique and f.index.is_monotonic_increasing
        assert np.isfinite(c[['open','high','low','close','volume','turnover']]).all().all()
        assert (c[['open','high','low','close']]>0).all().all() and (c[['volume','turnover']]>=0).all().all()
        assert (c.high>=c[['open','close','low']].max(axis=1)).all() and (c.low<=c[['open','close','high']].min(axis=1)).all()
        assert np.isfinite(f.funding_rate).all() and f.index.to_series().diff().max()==pd.Timedelta(hours=8)
        for p in [cp,fp]:inputs[str(p.relative_to(cache))]=sha(p)
        records.append(dict(symbol=s,minutes=len(c),first=str(c.index[0]),last=str(c.index[-1]),minutes_2026=int((c.index.year==2026).sum()),missing_minutes=0,invalid_ohlcv_rows=0,funding_events=len(f),funding_2026=int((f.index.year==2026).sum()),last_funding=str(f.index[-1]),max_funding_gap_hours=8,historical_funding_schedule_independently_verified=False))
    for p in sorted(ROOT.rglob('*.parquet')):
        if HERE in p.parents:continue
        names=pq.read_schema(p).names
        if 'entry' not in names:continue
        x=pd.to_datetime(pq.read_table(p,columns=['entry']).column('entry').to_numpy(),utc=True)
        inventory.append(dict(path=str(p.relative_to(ROOT)),rows=len(x),first=str(x.min()),last=str(x.max()),entries_2026=int((x.year==2026).sum())))
    pd.DataFrame(inventory).to_csv(HERE/'prior_entry_date_inventory.csv',index=False)
    result=dict(status='pass',method='Raw validity/counts and prior entry timestamps only; no new return scoring.',coverage=records,inputs=inputs,prior_ledger_files=len(inventory),prior_2026_entry_rows=sum(r['entries_2026'] for r in inventory),end_exclusive='2026-10-02T16:00:00+00:00',terminal_eight_hours_excluded_for_funding_coverage=True,holdout_untouched=False,reason='Original study generated full-span future-path opportunity summaries including 2026. Unknown external Grok use. Documented recent strategy runs exclude 2026.')
    (HERE/'DATA_AUDIT.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,required=True);a=p.parse_args();audit(a.cache)
