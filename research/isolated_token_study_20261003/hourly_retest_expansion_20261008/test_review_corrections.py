"""Focused pre-outcome tests for boundary handling and complete reporting."""
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import data_gate as gate
import run_expansion as runner
from test_run_expansion import fixture

def test_observed_edges_never_allow_interior_gap():
    old_begin,old_end=gate.BEGIN,gate.END
    gate.BEGIN=pd.Timestamp('2025-01-01',tz='UTC');gate.END=gate.BEGIN+pd.Timedelta(minutes=185)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';out=root/'out'
            (source/'minutes/AAAUSDT').mkdir(parents=True);(source/'funding').mkdir();(out/'funding').mkdir(parents=True)
            index=pd.date_range(gate.BEGIN+pd.Timedelta(minutes=2),gate.END,freq='min',inclusive='left')
            c=pd.DataFrame(dict(timestamp_ms=index.asi8//10**6,open=100.,high=101.,low=99.,close=100.,volume=1.,turnover=100.))
            path=source/'minutes/AAAUSDT/page.csv.gz';c.to_csv(path,index=False)
            f=pd.DataFrame(dict(timestamp_ms=[gate.BEGIN.value//10**6,gate.END.value//10**6],funding_rate=[.0001,.0001]));f.to_csv(source/'funding/AAAUSDT.csv.gz',index=False)
            result,_=gate.audit_symbol(source,out,'AAAUSDT',{'launchTime':'0','deliveryTime':'0'},True)
            assert result['candles']==120 and result['leading_partial_minutes_trimmed']==58 and result['trailing_partial_minutes_trimmed']==5
            terminal=f.copy();terminal['timestamp_ms']=[(gate.BEGIN-pd.Timedelta(hours=14)).value//10**6,(gate.BEGIN-pd.Timedelta(hours=6)).value//10**6]
            terminal.to_csv(source/'funding/AAAUSDT.csv.gz',index=False)
            capped,_=gate.audit_symbol(source,out,'AAAUSDT',{'launchTime':'0','deliveryTime':'0'},True)
            assert capped['candles']==60 and capped['terminal_funding_minutes_trimmed']==60
            f.to_csv(source/'funding/AAAUSDT.csv.gz',index=False)
            c=c[c.timestamp_ms!=(gate.BEGIN+pd.Timedelta(minutes=90)).value//10**6];c.to_csv(path,index=False)
            try:gate.audit_symbol(source,out,'AAAUSDT',{'launchTime':'0','deliveryTime':'0'},True)
            except ValueError as e:assert 'interior minute gap' in str(e)
            else:raise AssertionError('interior gap passed boundary amendment')
    finally:gate.BEGIN,gate.END=old_begin,old_end

def test_zero_signal_token_stays_in_universe_report():
    plans,opportunities,ledger=fixture()
    _,cells=runner.summary_tables(plans,opportunities,ledger,['AAAUSDT','ZZZUSDT'])
    zeros=cells[cells.symbol=='ZZZUSDT']
    assert len(zeros)==32 and (zeros.original_signals==0).all() and (zeros.admitted==0).all()
    assert 'signal_year' in cells and 'entry_year' not in cells

def test_marks_are_not_completed_wins():
    _,_,ledger=fixture();ledger=ledger.iloc[:2].copy()
    ledger.loc[ledger.index[0],'reason']='boundary_mtm'
    q=runner.metric_values(ledger,4)
    assert q['completed_trades']==1 and q['marks']==1
    assert q['completed_net_win_rate']==0 and q['net_win_rate']==.5
    assert np.isclose(q['closed_net_per_original_signal'],-.005)
    assert np.isclose(q['marked_net_return_sum'],.02)

if __name__=='__main__':
    for test in [test_observed_edges_never_allow_interior_gap,test_zero_signal_token_stays_in_universe_report,test_marks_are_not_completed_wins]:
        test();print('PASS',test.__name__)
