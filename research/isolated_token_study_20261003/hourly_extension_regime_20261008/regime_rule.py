"""Prior24h path efficiency; excludes signal hour; no fitted thresholds."""
import numpy as np
import pandas as pd
THRESHOLD=.30

def context(closes):
    net=(closes.shift(1)-closes.shift(25)).abs()
    path=closes.diff().abs().shift(1).rolling(24,min_periods=24).sum()
    er=(net/path.replace(0,np.nan)).mask(path==0,0.)
    return pd.DataFrame(dict(efficiency24_before_signal=er,directional=er>=THRESHOLD,
        regime_asof=closes.index-pd.Timedelta(hours=1)),index=closes.index)

def independent_at(minutes,entry):
    # C[T-1h] through C[T-25h] are minute closes at T-1h-1m,...
    times=pd.date_range(entry-pd.Timedelta(hours=25,minutes=1),periods=25,freq='h')
    if not times.isin(minutes.index).all():raise ValueError('missing causal closes')
    x=minutes.loc[times,'close'].to_numpy(float)
    path=sum(abs(float(x[j])-float(x[j-1])) for j in range(1,25))
    return abs(float(x[-1])-float(x[0]))/path if path else 0.

def policy_pass(passes_extension,directional,policy):
    e=np.asarray(passes_extension,bool);d=np.asarray(directional,bool)
    if policy=='none':return np.ones(e.shape,bool)
    if policy=='always':return e
    if policy=='directional':return ~d|e
    if policy=='loweff':return d|e
    raise ValueError(policy)
