"""Frozen research feature kernel, ported without arithmetic changes.

Source: MAR cipher study 2026-10-22, code/features.py. Only the optional
Numba decorator/import were removed. Input row i is a COMPLETED hourly bar
closing at seed_start_ms + i*HOUR; row zero is the empty seed boundary.
A NaN row is a missing complete bar, never an interpolated observation.
The caller must retain one fixed seed, not roll the EMA lookback each hour.
"""
import numpy as np
import pandas as pd

def ema_reset(x,n):
 out=np.empty(len(x));v=np.nan;alpha=2./(n+1.)
 for i in range(len(x)):
  if not np.isfinite(x[i]):v=np.nan
  elif not np.isfinite(v):v=x[i]
  else:v=alpha*x[i]+(1-alpha)*v
  out[i]=v
 return out

def rolling(x,n,kind='mean'):
 return getattr(pd.Series(x).rolling(n,min_periods=n),kind)().to_numpy()

def streak(x):
 out=np.zeros(len(x),np.int64)
 for i,v in enumerate(x):out[i]=(out[i-1] if i else 0)+1 if v else 0
 return out

def compute(b):
 h=len(b);op,hi,lo,cl,vol,turn=b.T
 valid=np.isfinite(b).all(1)
 p=(hi+lo+cl)/3;e=ema_reset(p,10);dev=ema_reset(np.abs(p-e),10)
 z=np.divide(p-e,.015*dev,out=np.zeros(h),where=dev!=0);z[~np.isfinite(dev)]=np.nan
 w1=ema_reset(z,21);w2=rolling(w1,4)
 previous=np.r_[np.nan,cl[:-1]];tr=np.maximum(hi-lo,np.maximum(np.abs(hi-previous),np.abs(lo-previous)))
 atr_prev=np.r_[np.nan,rolling(tr,14)[:-1]]
 m=np.divide(2*cl-hi-lo,hi-lo,out=np.zeros(h),where=hi!=lo);m[~valid]=np.nan
 vs=rolling(vol,21,'sum');cmf=np.divide(rolling(m*vol,21,'sum'),vs,out=np.full(h,np.nan),where=vs>0)
 pressure=rolling(m,21)
 h4=np.arange(4,h,4);c4=cl[h4].copy();full=np.array([valid[t-3:t+1].all() for t in h4]);c4[~full]=np.nan
 em4=ema_reset(c4,50);ct4=streak(full)
 context=np.full(h,-1,np.int64);ctxclose=np.full(h,np.nan);ctxema=np.full(h,np.nan);ctxprev=np.full(h,np.nan);ctxcount=np.zeros(h,np.int64)
 for t in range(h):
  j=np.searchsorted(h4,t-1,side='right')-1
  if j>=3 and 0<=t-1-h4[j]<4:
   context[t]=h4[j];ctxclose[t]=c4[j];ctxema[t]=em4[j];ctxprev[t]=em4[j-3];ctxcount[t]=ct4[j]
 ready=valid&(streak(valid)>=800)&(ctxcount>=200)&np.isfinite(atr_prev)&(atr_prev>0)
 up=(w1> w2)&(np.r_[np.nan,w1[:-1]]<=np.r_[np.nan,w2[:-1]])&(rolling(w1,3,'min')<=-60)
 dn=(w1< w2)&(np.r_[np.nan,w1[:-1]]>=np.r_[np.nan,w2[:-1]])&(rolling(w1,3,'max')>=60)
 side=np.where(ready&up,1,np.where(ready&dn,-1,0))
 cmfprev=np.r_[np.full(3,np.nan),cmf[:-3]];pprev=np.r_[np.full(3,np.nan),pressure[:-3]]
 flow=((side==1)&(cmf<0)&(cmf>cmfprev))|((side==-1)&(cmf>0)&(cmf<cmfprev))
 price=((side==1)&(pressure<0)&(pressure>pprev))|((side==-1)&(pressure>0)&(pressure<pprev))
 trend=((side==1)&(ctxclose>ctxema)&(ctxema>ctxprev))|((side==-1)&(ctxclose<ctxema)&(ctxema<ctxprev))
 stop=np.where(side==1,rolling(lo,12,'min')-.5*atr_prev,rolling(hi,12,'max')+.5*atr_prev)
 distance=side*(cl-stop);target=cl+side*2*distance
 # All attribution information is known before the setup candle begins.
 delta=np.abs(np.diff(cl,prepend=np.nan));den=rolling(delta,72,'sum');back=np.r_[np.full(72,np.nan),cl[:-72]]
 eff=np.divide(np.abs(cl-back),den,out=np.zeros(h),where=den>0);eff[~np.isfinite(den)]=np.nan;eff=np.r_[np.nan,eff[:-1]]
 ret=np.r_[np.nan,np.diff(np.log(cl))];rv=np.r_[np.nan,rolling(ret,72,'std')[:-1]]
 turn24=np.r_[np.nan,rolling(turn,24,'sum')[:-1]]
 return pd.DataFrame(dict(hour=np.arange(h),side=side,ready=ready,w1=w1,w2=w2,cmf=cmf,pressure=pressure,flow=flow,trend=trend,price=price,context_hour=context,close=cl,stop=stop,target=target,atr=atr_prev,efficiency=eff,volatility=rv,turnover=turn24))
