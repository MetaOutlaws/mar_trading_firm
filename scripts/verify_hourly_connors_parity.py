"""Offline research/runtime parity; run only against owner-held historical files."""
import argparse,json,sys
from dataclasses import replace
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.strategy.base import SignalSide
from core.strategy.hourly_compression_v1 import HourlyCompressionV1Strategy as Base
from core.strategy.hourly_compression_connors_v1 import HourlyCompressionConnorsV1Strategy as Rule

def main(cache,research,out):
    refs=pd.read_csv(research/'hourly_connors_filter_20261008/results_v1/crsi_entry_context.csv')
    refs['entry']=pd.to_datetime(refs.entry,utc=True)
    full=window=0;max_error=0.
    for symbol,g in refs.groupby('symbol'):
        c=pd.read_parquet(cache/f'{symbol}_1m.parquet')
        if not isinstance(c.index,pd.DatetimeIndex):raise ValueError('expected original datetime index')
        c=c[c.index<pd.Timestamp('2026-01-01',tz='UTC')]
        h=c.resample('h').agg(dict(open='first',high='max',low='min',close='last',volume='sum'))
        for side in [SignalSide.LONG,SignalSide.SHORT]:
            rule=Rule(replace(Rule().params,side=side));base=Base(replace(Base().params,side=side))
            out_full=rule.generate_signals(h);base_full=base.generate_signals(h)
            expect=(base_full.signal!=0)&out_full.passes_crsi
            assert np.array_equal(out_full.signal.to_numpy(),np.where(expect,side.sign,0))
            for r in g[g.side==side.sign].itertuples():
                t=r.entry-pd.Timedelta(hours=1);j=h.index.get_loc(t);q=out_full.loc[t]
                for col in ['filter_crsi','price_rsi3','streak_rsi2','rank100','streak','return1']:
                    assert np.isclose(q[col],getattr(r,col),atol=1e-9,rtol=1e-11),(symbol,t,col)
                assert bool(q.passes_crsi)==bool(r.passes_crsi)
                assert q.signal==(side.sign if r.passes_crsi else 0);full+=1
                tail=h.iloc[j-849:j+1];assert len(tail)==850
                w=rule.generate_signals(tail).iloc[-1]
                max_error=max(max_error,abs(w.filter_crsi-q.filter_crsi))
                assert np.isclose(w.filter_crsi,q.filter_crsi,atol=1e-9,rtol=1e-11)
                assert w.signal==q.signal and w.passes_crsi==q.passes_crsi;window+=1
    result=dict(status='pass',historical_entry_contexts=full,rolling_850_hour_checks=window,
        full_history_signal_frames=6,max_rolling_crsi_error=max_error,scope='entry rule parity, not production fills',scores_2026=False)
    assert full==window==143
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--cache',type=Path,required=True);p.add_argument('--research',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();main(a.cache,a.research,a.out)
