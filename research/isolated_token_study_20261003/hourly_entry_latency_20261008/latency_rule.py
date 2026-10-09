"""Delay execution of a frozen hourly signal; never inspect the waiting path."""
from numbers import Integral
import sys
from pathlib import Path
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'hourly_fill_brackets_20261008'))
from bracket_rule import raw_trade
DELAYS=(0,1,5,15)
PRIMARY_DELAY=5

def scheduled_index(index,signal_i,end,delay):
    if isinstance(delay,bool) or not isinstance(delay,Integral) or delay not in DELAYS:
        raise ValueError('delay must be one of 0,1,5,15 whole minutes')
    if not 0<=signal_i<end<=len(index):raise ValueError('invalid signal/path bounds')
    i=int(signal_i)+int(delay)
    if i>=end:return None
    if index[i]!=index[signal_i]+pd.Timedelta(minutes=int(delay)):
        raise ValueError('missing minute in delayed entry schedule')
    return i

def delayed_trade(t,signal_i,side,slip,end,delay):
    i=scheduled_index(t.index,signal_i,end,delay)
    if i is None:return None
    r=raw_trade(t,i,side,slip,end,'fill_brackets')
    return dict(r,signal_i=int(signal_i),delay_minutes=int(delay))
