#!/usr/bin/env python3
"""Public-data-only BL8 shadow worker; isolated DB; never calls an order API."""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from core.strategy.bl8 import decision
from core.execution.bl8_shadow import HOURLY_PAPER_STARTING_EQUITY, Ledger
from core.risk.limits import PAPER_LIMITS

ALLOWED={'instruments-info','kline','orderbook','funding/history'}


def now_ms(): return time.time_ns()//1_000_000


def public_get(path, **params):
    if path not in ALLOWED: raise ValueError('Only four public market-data endpoints are permitted')
    request=Request('https://api.bybit.com/v5/market/'+path+'?'+urlencode({'category':'linear',**params}),
                    headers={'User-Agent':'MAR-BL8-paper-validation/1'})
    with urlopen(request,timeout=5) as response: body=json.load(response)
    if body.get('retCode')!=0: raise ValueError(f'public market response {body.get("retCode")}')
    server=int(body['time']);received=now_ms()
    if not 0<=received-server<=5000: raise ValueError('server clock/response age mismatch')
    return body


def context(symbol, asof):
    instrument=public_get('instruments-info',symbol=symbol)['result']['list']
    matches=[x for x in instrument if x.get('symbol')==symbol]
    if len(matches)!=1 or matches[0].get('status')!='Trading':
        return {'symbol':symbol,'eligible_signal':False,'reason':'instrument_unavailable','instrument':matches}
    histories=[];raw=[]
    for interval,duration in [('60',3_600_000),('240',14_400_000)]:
        data=public_get('kline',symbol=symbol,interval=interval,end=asof-1,limit=40);raw.append(data)
        bars=[{'t':int(r[0])+duration,**dict(zip('ohlc',map(float,r[1:5])))} for r in data['result']['list'] if int(r[0])+duration<=asof]
        bars.sort(key=lambda b:b['t']);histories.append(bars)
    return decision(symbol,*histories,asof)|{'instrument':matches[0],'raw_context':raw}


def quote(symbol):
    b=public_get('orderbook',symbol=symbol,limit=200)['result']
    if b.get('s')!=symbol: raise ValueError('wrong symbol')
    # Matching-engine generation time when available; never a locally fabricated time.
    b['snapshot_ts']=b['ts'];b['ts']=b.get('cts',b['ts']);return b


def funding_snapshot(position, interval_minutes):
    end=position['exit_ms'] or now_ms();start=position['entry_ms'];cursor=end;rates={}
    for _ in range(200):
        data=public_get('funding/history',symbol=position['symbol'],startTime=start,endTime=cursor,limit=200)
        rows=data['result']['list']
        for r in rows:
            if r.get('symbol')!=position['symbol']: raise ValueError('funding symbol mismatch')
            t=int(r['fundingRateTimestamp']);rate=float(r['fundingRate'])
            if start<t<=end:
                if t in rates and rates[t]!=rate: raise ValueError('conflicting funding rates')
                rates[t]=rate
        if len(rows)<200: break
        nxt=min(int(r['fundingRateTimestamp']) for r in rows)-1
        if nxt>=cursor: raise ValueError('funding pagination stalled')
        cursor=nxt
    else: raise ValueError('funding history pagination limit')
    result=[]
    for t,rate in sorted(rates.items()):
        minute=t//60_000*60_000
        candles=public_get('kline',symbol=position['symbol'],interval='1',start=minute,end=minute,limit=1)['result']['list']
        if len(candles)!=1 or int(candles[0][0])!=minute: raise ValueError('missing funding price proxy')
        result.append({'t':t,'rate':rate,'price':float(candles[0][1]),'basis':'settlement-minute-open-proxy'})
    interval=int(interval_minutes)*60_000
    if interval<=0: raise ValueError('unknown funding interval')
    expected=set(range((start//interval+1)*interval,end+1,interval))
    # A varying schedule or missing settlement remains unknown, never assumed zero.
    complete=set(rates)==expected
    return end,result,complete


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--db',type=Path,required=True)
    parser.add_argument('--config',type=Path,default=ROOT/'config/sleeves/mar_bl8_shadow_v1.json')
    parser.add_argument('--audit',action='store_true');args=parser.parse_args()
    raw=args.config.read_bytes();config=json.loads(raw);sha=hashlib.sha256(raw).hexdigest()
    if config.get('mode')!='paper_shadow' or config.get('live_authorized') is not False:
        raise ValueError('paper-only config required')
    if config.get('initial_price_stop_risk_usdt') is not None:
        raise ValueError('fixed one-USDT unit is not the sizing rule')
    if config.get('sizing_policy')!='hourly_paper_limits':
        raise ValueError('paper limits sizing policy required')
    expected={
        'starting_equity_usdt':HOURLY_PAPER_STARTING_EQUITY,
        'max_risk_per_trade_pct':PAPER_LIMITS.max_risk_per_trade_pct,
        'max_position_pct':PAPER_LIMITS.max_position_pct,
        'max_total_exposure_pct':PAPER_LIMITS.max_total_exposure_pct,
        'max_leverage':PAPER_LIMITS.max_leverage,
        'min_notional_usdt':PAPER_LIMITS.min_notional_usdt,
        'account_risk_fraction':PAPER_LIMITS.max_risk_per_trade_pct,
    }
    for key,value in expected.items():
        got=config.get(key)
        if not isinstance(got,(int,float)) or not math.isclose(float(got),float(value),rel_tol=0,abs_tol=0):
            raise ValueError(f'frozen paper limit {key} changed')
    if config.get('entry_market_slippage')!=.002 or config.get('fee_per_side')!=.00055 or config.get('price_stop_min_fraction')!=.08:
        raise ValueError('frozen test units/costs changed')
    args.db.parent.mkdir(parents=True,exist_ok=True)
    lock=(args.db.parent/'worker.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    ledger=Ledger(args.db,sha,starting_equity=float(config['starting_equity_usdt']),limits=PAPER_LIMITS)
    if args.audit: print(json.dumps(ledger.audit(),indent=2));return
    release=(ROOT/'BL8_RELEASE_SHA').read_text().strip() if (ROOT/'BL8_RELEASE_SHA').exists() else 'local_unpublished'
    started=now_ms();ledger.observe(started,'startup',{'config_sha':sha,'release':release,'pid':os.getpid(),'paper_only':True})
    jobs={};queued=set();last_hour=None;last_quote=0;last_funding=0;last_status=0;instruments={};last_loop=started
    with cf.ThreadPoolExecutor(max_workers=12) as scan_pool, cf.ThreadPoolExecutor(max_workers=12) as exit_pool, cf.ThreadPoolExecutor(max_workers=4) as funding_pool:
      while True:
        now=now_ms();hour=now//3_600_000*3_600_000
        if now-last_loop>15_000: ledger.observe(now,'supervision_gap',{'milliseconds':now-last_loop})
        last_loop=now
        if hour!=last_hour:
            last_hour=hour
            for symbol in config['universe']:
                job=scan_pool.submit(context,symbol,hour);jobs[job]=('context',symbol)
        for job in list(jobs):
            if not job.done(): continue
            kind,identity=jobs.pop(job);queued.discard((kind,identity));observed=now_ms()
            try:
                value=job.result()
                if kind=='context':
                    ledger.observe(observed,'context',value)
                    if isinstance(value.get('instrument'),dict): instruments[identity]=value['instrument']
                    ledger.signal(value,observed)
                elif kind=='quote':
                    ledger.observe(observed,'quote',value)
                    for p in ledger.positions():
                        if p['symbol']==identity:
                            ledger.mark(p['uid'],value,observed)
                            ledger.exit(p['uid'],value,observed)
                    for signal in ledger.signals():
                        if signal['symbol']==identity and identity in instruments:
                            ledger.enter(signal,value,instruments[identity],observed,entries_enabled=not(args.db.parent/'entries_disabled').exists())
                elif kind=='funding':
                    through,settlements,complete=value;ledger.funding(identity,through,settlements,complete=complete)
            except Exception as exc:
                ledger.observe(observed,'error',{'operation':kind,'identity':identity,'error':f'{type(exc).__name__}: {exc}'})
        if now-last_quote>=5000:
            last_quote=now;symbols={p['symbol'] for p in ledger.positions()}
            for s in ledger.signals():
                if now>s['action_ms']+60_000: ledger.reject(s,now,'missed_action')
                elif now>=s['action_ms']: symbols.add(s['symbol'])
            for symbol in sorted(symbols):
                if ('quote',symbol) not in queued:
                    job=exit_pool.submit(quote,symbol);jobs[job]=('quote',symbol);queued.add(('quote',symbol))
        if now-last_funding>=300_000:
            last_funding=now
            ps=ledger.positions()+[p for p in ledger.positions('closed') if p['funding_status']!='observed_through_exit']
            for p in ps:
                if p['symbol'] not in instruments: continue
                if ('funding',p['uid']) not in queued:
                    interval=instruments[p['symbol']].get('fundingInterval',0)
                    job=funding_pool.submit(funding_snapshot,p,interval);jobs[job]=('funding',p['uid']);queued.add(('funding',p['uid']))
        if now-last_status>=10_000:
            last_status=now;status={'heartbeat_ms':now,'started_ms':started,'config_sha':sha,'release':release,'jobs':len(jobs),'paper_only':True,'audit':ledger.audit()}
            status['equity']=ledger.equity(now)
            status['entry_decisions']={r[0]:r[1] for r in ledger.db.execute('SELECT status,count(*) FROM signals GROUP BY status')}
            tmp=args.db.parent/'status.tmp';tmp.write_text(json.dumps(status,indent=2));os.replace(tmp,args.db.parent/'status.json')
        time.sleep(1)


if __name__=='__main__': main()
