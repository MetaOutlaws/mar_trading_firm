"""Owner-approved standalone Connors gate on frozen hourly compression, PAPER only."""
import numpy as np
import pandas as pd
from core.strategy.hourly_compression_v1 import HourlyCompressionV1Strategy


def component_rsi(values, period):
    """Wilder RSI seeded by the first period changes; flat = 50."""
    x=np.asarray(values,float)
    result=np.full(len(x),np.nan)
    if len(x)<=period:return result
    changes=np.diff(x);up=np.maximum(changes,0);down=np.maximum(-changes,0)
    gain=up[:period].mean();loss=down[:period].mean()
    for j in range(period,len(x)):
        if j>period:
            gain=((period-1)*gain+up[j-1])/period
            loss=((period-1)*loss+down[j-1])/period
        result[j]=100*gain/(gain+loss) if gain+loss else 50.
    return result


def connors_components(closes):
    x=np.asarray(closes,float)
    if not np.isfinite(x).all() or (x<=0).any():raise ValueError('finite positive closes required')
    streak=np.zeros(len(x))
    for j in range(1,len(x)):
        if x[j]>x[j-1]:streak[j]=streak[j-1]+1 if streak[j-1]>0 else 1
        elif x[j]<x[j-1]:streak[j]=streak[j-1]-1 if streak[j-1]<0 else -1
    returns=np.r_[np.nan,x[1:]/x[:-1]-1] if len(x) else np.array([])
    rank=np.full(len(x),np.nan)
    for j in range(101,len(x)):
        rank[j]=np.count_nonzero(returns[j-100:j]<returns[j])
    price=component_rsi(x,3);streak_rsi=component_rsi(streak,2)
    return pd.DataFrame(dict(filter_crsi=(price+streak_rsi+rank)/3,price_rsi3=price,
        streak_rsi2=streak_rsi,rank100=rank,streak=streak,return1=returns),index=closes.index)


def connors_gate(values,side):
    if side not in (-1,1):raise ValueError('LONG or SHORT required')
    x=np.asarray(values,float)
    return np.isfinite(x)&(x>=0)&(x<=100)&((x<=90) if side==1 else (x>=10))


class HourlyCompressionConnorsV1Strategy(HourlyCompressionV1Strategy):
    name='hourly_compression_connors_v1'

    def generate_signals(self,candles):
        out=super().generate_signals(candles)
        context=connors_components(candles.close)
        allowed=connors_gate(context.filter_crsi,self.params.side.sign)
        blocked=(out.signal!=0)&~allowed
        empty=self.empty_signals(candles)
        for col in ['signal','side','score','reason']:
            out.loc[blocked,col]=empty.loc[blocked,col]
        for col in context:out[col]=context[col]
        out['passes_crsi']=allowed
        out.loc[out.signal!=0,'reason']='hourly compression v1 + CRSI(3,2,100): LONG<=90 / SHORT>=10'
        return out
