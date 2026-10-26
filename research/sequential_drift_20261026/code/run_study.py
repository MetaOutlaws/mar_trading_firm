"""Frozen CUSUM discovery screen. No account ROI or broker operations."""
from pathlib import Path
import argparse, hashlib, json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT.parent / 'restored/MAR_relative_value_checkpoint_20261020'
OUT = ROOT / 'results'
START = pd.Timestamp('2022-01-01', tz='UTC')
N = 2103840
FEE = .00055
# entry/regular exit slippage, protective-stop slippage; fee is separate.
COSTS = {'baseline': (.002, 0.), 'moderate': (.003, .002),
         'desk': (.00255, .00255), 'severe': (.01, .01)}
ARMS = {'S01': 3., 'S00': np.inf}
CASES = [(c, d) for c in COSTS for d in ([1] if c == 'severe' else [1, 6])]

def features(hc, cap):
    """Daily observation d is known at minute 1440*d; scale excludes that day."""
    hc = np.asarray(hc, float)
    D = (len(hc)-1)//24
    close = hc[::24].copy()
    valid = np.zeros(D+1, bool)
    for d in range(1, D+1):
        valid[d] = np.isfinite(hc[(d-1)*24+1:d*24+1]).all()
    close[~valid] = np.nan
    r = np.full(D+1, np.nan)
    r[1:] = np.log(close[1:]/close[:-1])
    sigma = pd.Series(r).rolling(60, min_periods=60).std(ddof=0).shift(1).to_numpy()
    z = np.divide(r, sigma, out=np.full_like(r, np.nan), where=sigma>0)
    signal, plus, minus = cusum(z, cap)
    return close, sigma, z, signal, plus, minus

def cusum(z, cap):
    signal = np.zeros(len(z), np.int8)
    plus, minus = np.zeros(len(z)), np.zeros(len(z))
    p = m = 0.
    for i, raw in enumerate(z):
        if not np.isfinite(raw):
            p = m = 0.
            plus[i] = minus[i] = np.nan
            continue
        v = np.clip(raw, -cap, cap)
        p, m = max(0., p+v-.5), max(0., m-v-.5)
        plus[i], minus[i] = p, m
        if p >= 5.:
            signal[i] = 1
        elif m >= 5.:
            signal[i] = -1
        if signal[i]:
            p = m = 0.
    return signal, plus, minus

def raw_path(opens, funding_ok, signal, sigma, d, side, stop, delay):
    e = d*1440 + delay
    future = np.arange(d+1, len(signal))
    exit_days = future[(signal[future] == -side) | ~np.isfinite(sigma[future])]
    scheduled = int(exit_days[0]*1440+delay) if len(exit_days) else len(opens)-1
    scheduled = min(scheduled, len(opens)-1)
    bad = np.flatnonzero(~np.isfinite(opens[e+1:scheduled+1]) | ~funding_ok[e+1:scheduled+1])
    first_bad = int(e+1+bad[0]) if len(bad) else len(opens)
    stop_hits = np.flatnonzero(side*(opens[e+1:scheduled+1]-stop) <= 0)
    hit = int(e+1+stop_hits[0]) if len(stop_hits) else len(opens)
    if first_bad <= min(hit, scheduled):
        return first_bad-1, 'data_censor'
    if hit <= scheduled:
        x = min(hit+1, len(opens)-1)
        if not np.isfinite(opens[x]) or not funding_ok[x]:
            return hit, 'data_censor'
        return x, 'stop' if hit+1 < len(opens) else 'terminal'
    return scheduled, ('opposite_signal' if len(exit_days) and scheduled < len(opens)-1
                       and signal[exit_days[0]] == -side else
                       'invalid_feature' if len(exit_days) and scheduled < len(opens)-1 else 'terminal')

def economics(side, raw_entry, raw_exit, stop, slip, stop_slip, reason, funding_unit):
    ep = raw_entry*(1+side*slip)
    xp = raw_exit*(1-side*(stop_slip if reason=='stop' else slip))
    qty = 1000./ep
    gross = side*(raw_exit-raw_entry)*qty
    slippage = gross-side*(xp-ep)*qty
    fees = FEE*qty*(ep+xp)
    funding = side*qty*funding_unit
    risk = qty*side*(ep-stop)
    stop_fill = stop*(1-side*stop_slip)
    planned = qty*(side*(ep-stop_fill)+FEE*(ep+stop_fill))
    net = gross-slippage-fees-funding
    return dict(entry_price=ep, exit_price=xp, quantity=qty, gross=gross,
                slippage=slippage, fees=fees, funding_cost=funding,
                net=net, risk=risk, planned_risk=planned, net_R=net/risk)

def main():
    freeze = json.loads((ROOT/'FREEZE.json').read_text())
    for p, h in freeze['files'].items():
        assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest() == h, p
    uni = pd.read_csv(DATA/'results/universe.csv')
    rows, decisions, feats, audits, token_daily = [], [], [], [], []
    curves = {(arm,c,d):np.zeros(N) for arm in ARMS for c,d in CASES}
    rcurves = {k:np.zeros(N) for k in curves}
    btc = np.load(DATA/'cache/BTCUSDT.npz')['hourly_close']
    # Marked, overlapping fixed-notional opportunity ledgers, NOT funded portfolios.
    for si,u in enumerate(uni.itertuples()):
        f = DATA/'cache'/f'{u.symbol}.npz'
        zf = np.load(f); op = zf['opens']; hc=zf['hourly_close']
        fi,fr = zf['funding_index'],zf['funding_rate']
        assert len(op)==N and len(hc)==N//60+1
        fgood=np.isfinite(op[fi]) & np.isfinite(fr)
        funding_event=np.zeros(N); np.add.at(funding_event,fi[fgood],op[fi[fgood]]*fr[fgood])
        fc=np.cumsum(funding_event)
        j=np.searchsorted(fi,np.arange(N),side='right')-1
        funding_ok=(j>=0)&(np.arange(N)-fi[np.maximum(j,0)]<=480)&fgood[np.maximum(j,0)]
        symbol_rows=[]
        for arm,cap in ARMS.items():
            close,sigma,z,sig,plus,minus=features(hc,cap)
            for d in np.flatnonzero(sig):
                feats.append(dict(symbol=u.symbol,arm=arm,day=int(d),side=int(sig[d]),sigma=float(sigma[d]),z=float(z[d]),plus=float(plus[d]),minus=float(minus[d])))
            # Prefix invariance at fixed calendar cutoffs, including unavailable history.
            for hd in (365*24, 731*24, 1096*24):
                ff=features(hc[:hd+1],cap)
                for a,b in zip(ff,(close,sigma,z,sig,plus,minus)):
                    assert np.allclose(a,b[:len(a)],equal_nan=True)
            for cost,delay in CASES:
                slip,stop_slip=COSTS[cost]; busy=-1; censored=False
                curve=curves[(arm,cost,delay)]; rcurve=rcurves[(arm,cost,delay)]
                token_curve=np.zeros(N//1440);token_rcurve=np.zeros(N//1440)
                endpoints=np.arange(1439,N,1440)
                for d in np.flatnonzero(sig):
                    e=int(d*1440+delay);side=int(sig[d]);why='admitted'
                    if censored:why='after_data_censor'
                    elif e<=busy:why='token_busy'
                    elif e>=N:why='outside_window'
                    elif not np.isfinite(op[e]) or not funding_ok[e]:why='entry_data_unavailable'
                    if why!='admitted':
                        decisions.append(dict(symbol=u.symbol,arm=arm,cost=cost,delay=delay,day=int(d),decision=why));continue
                    distance=2*sigma[d]; raw=op[e];stop=raw*(1-side*distance)
                    ep=raw*(1+side*slip);stop_pct=side*(ep-stop)/ep
                    if not .005<=stop_pct<=.15 or stop<=0:
                        decisions.append(dict(symbol=u.symbol,arm=arm,cost=cost,delay=delay,day=int(d),decision='stop_bound'));continue
                    x,reason=raw_path(op,funding_ok,sig,sigma,int(d),side,stop,delay)
                    econ=economics(side,raw,op[x],stop,slip,stop_slip,reason,fc[x]-fc[e])
                    h=int(d)*24; br=np.log(btc[h]/btc[h-168]) if h>=168 and np.isfinite(btc[h-168:h+1]).all() else np.nan
                    regime='up' if br>=np.log(1.05) else 'down' if br<=np.log(.95) else 'sideways' if np.isfinite(br) else 'unknown'
                    row=dict(symbol=u.symbol,sector=u.sector,arm=arm,cost=cost,delay=delay,day=int(d),e=e,x=x,side=side,stop=stop,stop_pct=stop_pct,reason=reason,duration_days=(x-e)/1440,year=(START+pd.Timedelta(minutes=e)).year,week=int(e//10080),regime=regime,sigma=float(sigma[d]),z=float(z[d]),**econ)
                    rows.append(row);symbol_rows.append(row)
                    decisions.append(dict(symbol=u.symbol,arm=arm,cost=cost,delay=delay,day=int(d),decision='admitted'))
                    q=econ['quantity'];mark=side*q*(op[e:x+1]-econ['entry_price'])-FEE*1000-side*q*(fc[e:x+1]-fc[e])
                    assert np.isfinite(mark).all()
                    mark[-1]=econ['net']
                    curve[e:x+1]+=mark;curve[x+1:]+=econ['net']
                    rcurve[e:x+1]+=mark/econ['risk'];rcurve[x+1:]+=econ['net_R']
                    inside=(endpoints>=e)&(endpoints<=x)
                    token_curve[inside]+=mark[endpoints[inside]-e]
                    token_curve[endpoints>x]+=econ['net']
                    token_rcurve[inside]+=mark[endpoints[inside]-e]/econ['risk']
                    token_rcurve[endpoints>x]+=econ['net_R']
                    busy=x
                    if reason=='data_censor':censored=True
                token_daily.append(pd.DataFrame(dict(symbol=u.symbol,sector=u.sector,arm=arm,cost=cost,delay=delay,day=np.arange(N//1440),net=np.diff(np.r_[0.,token_curve]),net_R=np.diff(np.r_[0.,token_rcurve]))))
        audits.append(dict(symbol=u.symbol,cache_sha256=hashlib.sha256(f.read_bytes()).hexdigest(),finite_minutes=int(np.isfinite(op).sum()),funding_rows=len(fi),prefix_checks=6,events=len(symbol_rows)))
        if (si+1)%12==0:print(f'{si+1}/96 tokens; {len(rows)} cost/timing event rows',flush=True)
    df=pd.DataFrame(rows);df.to_parquet(OUT/'events.parquet',index=False)
    pd.DataFrame(decisions).to_parquet(OUT/'decisions.parquet',index=False)
    pd.DataFrame(feats).to_parquet(OUT/'signals.parquet',index=False)
    pd.concat(token_daily,ignore_index=True).to_parquet(OUT/'token_daily.parquet',index=False)
    daily=[];drawdowns=[]
    for k,curve in curves.items():
        arm,cost,delay=k;sub=df[(df.arm==arm)&(df.cost==cost)&(df.delay==delay)]
        assert abs(curve[-1]-sub.net.sum())<1e-6
        rc=rcurves[k];assert abs(rc[-1]-sub.net_R.sum())<1e-6
        endpoints=np.arange(1439,N,1440);dp=np.diff(np.r_[0.,curve[endpoints]]);dr=np.diff(np.r_[0.,rc[endpoints]])
        for day, (p,r) in enumerate(zip(dp,dr)):daily.append(dict(arm=arm,cost=cost,delay=delay,day=day,net=p,net_R=r))
        for period,start,end in [('2022-25',0,N),('2023-25',365*1440,N)]+[(str(y),int((pd.Timestamp(f'{y}-01-01',tz='UTC')-START).total_seconds()/60),int((pd.Timestamp(f'{y+1}-01-01',tz='UTC')-START).total_seconds()/60)) for y in range(2022,2026)]:
            cv=np.r_[curve[start-1] if start else 0.,curve[start:end]];rv=np.r_[rc[start-1] if start else 0.,rc[start:end]]
            drawdowns.append(dict(arm=arm,cost=cost,delay=delay,period=period,opportunity_drawdown_usdt=float(np.max(np.maximum.accumulate(cv)-cv)),opportunity_drawdown_R=float(np.max(np.maximum.accumulate(rv)-rv))))
    pd.DataFrame(daily).to_parquet(OUT/'daily.parquet',index=False)
    pd.DataFrame(drawdowns).to_csv(OUT/'experimental_drawdown.csv',index=False)
    (OUT/'RUN_VERIFICATION.json').write_text(json.dumps({'symbols':len(audits),'prefix_checks':sum(a['prefix_checks'] for a in audits),'all_end_curves_reconcile':True,'historical_2026_opened':False,'audit':audits},indent=2))
    print('Completed',len(df),'event rows',flush=True)

if __name__=='__main__':main()
