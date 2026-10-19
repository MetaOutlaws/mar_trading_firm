#!/usr/bin/env python3
"""Isolated public-only forward worker. Does not connect to the current broker."""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import fcntl
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlencode

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from core.execution.bl8_public import PublicClient
from core.execution.recovery_paper import PaperTrial, BOOKS, MINUTE, canonical, fresh_quote, funding_known
from core.execution.recovery_feed import SignalFeed, advance_retest, HOUR

ALLOWED=frozenset(('instruments-info','kline','orderbook','funding/history'))


def now_ms():
    return time.time_ns()//1_000_000


class Market:
    def __init__(self, interval=.2, concurrency=2):
        self.client=PublicClient(min_interval_s=interval,concurrency=concurrency,
                                 max_attempts=3,header_cap_s=30)

    def get(self, path, **params):
        if path not in ALLOWED:
            raise ValueError('only allowlisted public market GETs are permitted')
        body=self.client.get('https://api.bybit.com/v5/market/'+path+'?'+
            urlencode(dict(category='linear',**params)),{'User-Agent':'MAR-recovery-paper/1'})
        if not 0<=now_ms()-int(body['time'])<=5000:
            raise ValueError('stale response or clock mismatch')
        return body

    def quote(self,symbol):
        q=self.get('orderbook',symbol=symbol,limit=200)['result']
        q['snapshot_ts']=q['ts'];q['ts']=q.get('cts',q['ts'])
        fresh_quote(q,symbol,now_ms())
        return q

    def funding(self,symbol,start,end):
        rates={};cursor=end
        for _ in range(200):
            rows=self.get('funding/history',symbol=symbol,startTime=start,endTime=cursor,limit=200)['result']['list']
            for row in rows:
                if row['symbol']!=symbol:
                    raise ValueError('funding symbol mismatch')
                t=int(row['fundingRateTimestamp']);rate=float(row['fundingRate'])
                if start<t<=end:
                    if t in rates and rates[t]!=rate:
                        raise ValueError('conflicting funding rate')
                    rates[t]=rate
            if len(rows)<200: break
            nxt=min(int(row['fundingRateTimestamp']) for row in rows)-1
            if nxt>=cursor: raise ValueError('funding cursor stalled')
            cursor=nxt
        else: raise ValueError('funding pagination exhausted')
        values=[]
        for t,rate in sorted(rates.items()):
            minute=t//MINUTE*MINUTE
            rows=self.get('kline',symbol=symbol,interval='1',start=minute,end=minute,limit=1)['result']['list']
            if len(rows)!=1 or int(rows[0][0])!=minute:
                raise ValueError('missing settlement minute open')
            values.append(dict(t=t,rate=rate,price=float(rows[0][1])))
        return dict(through_ms=end,rows=values,basis='settlement-minute-open-proxy')


def scan(feed,asof):
    histories={};observations=[];instruments={};pending=[];ready=[]
    with cf.ThreadPoolExecutor(max_workers=6) as pool:
        jobs={pool.submit(feed.histories,s,asof):s for s in feed.universe}
        for job in cf.as_completed(jobs):
            symbol=jobs[job]
            try:
                histories[symbol]=job.result()
            except Exception as exc:
                observations.append(dict(symbol=symbol,error=f'{type(exc).__name__}: {exc}'))
        btc=histories.get('BTCUSDT',{}).get('hours',[])
        jobs={pool.submit(feed.evaluate,h,btc,asof):s for s,h in histories.items()}
        for job in cf.as_completed(jobs):
            symbol=jobs[job]
            try:
                p,r,o=job.result();pending.extend(p);ready.extend(r);observations.extend(o)
                instrument=histories[symbol].get('instrument')
                if instrument: instruments[symbol]=instrument
            except Exception as exc:
                observations.append(dict(symbol=symbol,error=f'{type(exc).__name__}: {exc}'))
    return dict(hour=asof,pending=pending,ready=ready,observations=observations,
                instruments=instruments,coverage=len(histories),universe=len(feed.universe))


def retests(feed,pending,minute):
    next_pending={};ready={};observations=[]
    with cf.ThreadPoolExecutor(max_workers=4) as pool:
        jobs={pool.submit(feed.retest_bars,s,minute):s for s in {p['symbol'] for p in pending.values()}}
        bars={}
        for job in cf.as_completed(jobs):
            symbol=jobs[job]
            try: bars[symbol]=job.result()
            except Exception as exc: observations.append(dict(symbol=symbol,error=str(exc)))
    for uid,p in pending.items():
        if p['symbol'] not in bars:
            next_pending[uid]=p
            continue
        p2,s,reason=advance_retest(p,bars[p['symbol']],minute)
        if p2: next_pending[uid]=p2
        if s: ready[uid]=s
        if reason!='pending': observations.append(dict(uid=uid,reason=reason))
    return dict(pending=next_pending,ready=ready,observations=observations,minute=minute)


def atomic_json(path,value):
    tmp=path.with_suffix('.tmp')
    with tmp.open('w') as handle:
        handle.write(json.dumps(value,indent=2,allow_nan=False)+'\n');handle.flush();os.fsync(handle.fileno())
    os.replace(tmp,path)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--db',type=Path,required=True)
    parser.add_argument('--config',type=Path,default=ROOT/'config/sleeves/mar_recovery_paper_v1.json')
    parser.add_argument('--context-root',type=Path,default=Path('/context'))
    parser.add_argument('--initialize',action='store_true')
    parser.add_argument('--audit',action='store_true')
    args=parser.parse_args()
    if os.environ.get('TRADING_MODE','paper').lower()!='paper' or os.environ.get('GO_LIVE_CONFIRMED'):
        raise ValueError('paper only')
    args.db.parent.mkdir(parents=True,exist_ok=True)
    lock=(args.db.parent/'worker.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    ledger=PaperTrial(args.db,json.loads(args.config.read_text()),create=args.initialize)
    if args.initialize or args.audit:
        print(json.dumps(ledger.report(now_ms()),indent=2));return
    started=now_ms()
    release=(ROOT/'RECOVERY_RELEASE_SHA').read_text().strip() if (ROOT/'RECOVERY_RELEASE_SHA').is_file() else 'unpublished'
    first_hour=ledger.feed('first_forward_hour')
    if first_hour is None:
        first_hour=(started//HOUR+1)*HOUR
        ledger.save_feed('first_forward_hour',first_hour)
    pending=ledger.feed('pending',{});ready=ledger.feed('ready',{})
    instruments=ledger.feed('instruments',{})
    market=Market();funded_market=Market(.125,8);opportunity_market=Market(.2,4)
    funding_market=Market(.25,2)
    feed=SignalFeed(market.get,ledger.config['universe'],args.context_root)
    quotes={};settlements={};jobs={};busy=set();last_requested_hour=None
    retest_minute=None;retest_complete=None;last_quote={};last_funding={};last_status=0
    last_scan=ledger.feed('last_scan',{})
    ledger.observe(started,'startup',dict(release=release,first_forward_hour=first_hour,paper_only=True))
    with cf.ThreadPoolExecutor(max_workers=2) as work_pool, cf.ThreadPoolExecutor(max_workers=8) as quote_pool, \
         cf.ThreadPoolExecutor(max_workers=4) as opportunity_pool, cf.ThreadPoolExecutor(max_workers=2) as funding_pool:
        while True:
            now=now_ms();minute=now//MINUTE*MINUTE;hour=now//HOUR*HOUR
            for job in list(jobs):
                if not job.done(): continue
                kind,key=jobs.pop(job);busy.discard((kind,key))
                try:
                    result=job.result()
                    if kind=='scan':
                        instruments.update(result['instruments'])
                        if result['hour']>=first_hour:
                            pending.update({p['uid']:p for p in result['pending']})
                            ready.update({s['uid']:s for s in result['ready']})
                            retest_minute=None
                        for observation in result['observations']:
                            ledger.observe(now,'scan',observation|dict(hour=result['hour']))
                        last_scan={k:result[k] for k in ('hour','coverage','universe')}
                        last_scan['errors']=sum('error' in o or
                            str(o.get('reason','')).startswith('l01_') and o.get('reason')!='l01_long_trend_gate'
                            for o in result['observations'])
                        last_scan['completed_ms']=now
                    elif kind=='retest':
                        # Remove only the UIDs included in this job; retain a
                        # new hourly scan that completed while it was running.
                        for uid in key: pending.pop(uid,None)
                        pending.update(result['pending']);ready.update(result['ready'])
                        retest_complete=result['minute']
                        for o in result['observations']: ledger.observe(now,'retest',o)
                    elif kind=='quote': quotes[key]=result
                    elif kind=='funding': settlements[key]=result
                except Exception as exc:
                    ledger.observe(now,'error',dict(operation=kind,key=str(key),error=f'{type(exc).__name__}: {exc}'))
            if hour!=last_requested_hour and not any(k=='scan' for k,_ in busy):
                last_requested_hour=hour
                job=work_pool.submit(scan,feed,hour);jobs[job]=('scan',hour);busy.add(('scan',hour))
            if pending and retest_minute!=minute and not any(k=='retest' for k,_ in busy):
                retest_minute=minute;key=tuple(sorted(pending))
                job=work_pool.submit(retests,feed,dict(pending),minute)
                jobs[job]=('retest',key);busy.add(('retest',key))
            if not pending: retest_complete=minute
            positions=ledger.positions()
            funded={p['symbol'] for p in positions if p['book'] in BOOKS and p['status']=='open'}
            active={p['symbol'] for p in positions if p['status']=='open'}
            due=[s for s in ready.values() if s['action_ms']<=now]
            entry_symbols={s['symbol'] for s in due if now<s['action_ms']+MINUTE}
            priority=funded|entry_symbols
            for symbol in sorted(priority)+sorted(active-priority):
                if now-last_quote.get(symbol,0)<3000 or ('quote',symbol) in busy: continue
                last_quote[symbol]=now
                pool,source=(quote_pool,funded_market) if symbol in priority else (opportunity_pool,opportunity_market)
                job=pool.submit(source.quote,symbol);jobs[job]=('quote',symbol);busy.add(('quote',symbol))
            needed={p['symbol'] for p in positions if not funding_known(p,p['exit_ms'] or now)}
            for symbol in sorted(needed):
                if now-last_funding.get(symbol,0)<30000 or ('funding',symbol) in busy: continue
                last_funding[symbol]=now
                start=min(p['entry_ms'] for p in positions if p['symbol']==symbol)
                job=funding_pool.submit(funding_market.funding,symbol,start,now)
                jobs[job]=('funding',symbol);busy.add(('funding',symbol))
            batch=[]
            scan_ready=last_scan.get('hour')==hour
            if due and retest_complete==minute and scan_ready:
                all_quotes=all(s['symbol'] in quotes and 0<=now-int(quotes[s['symbol']]['ts'])<=4000 for s in due)
                if all_quotes or now-minute>=50000:
                    batch=due
            try:
                ledger.cycle(f'cycle:{now}',now,quotes,instruments,batch,settlements,
                             manual_halt=(args.db.parent/'entries_disabled').exists())
            except Exception as exc:
                # A ledger/input conflict must never be bypassed by subsequent
                # admissions. Keep supervision and exits running with the halt.
                (args.db.parent/'entries_disabled').touch(exist_ok=True)
                ledger.observe(now,'cycle_error',dict(error=f'{type(exc).__name__}: {exc}'))
                for s in batch:
                    ledger.observe(now,'quarantined_candidate',s)
                settlements.clear()
            for s in batch: ready.pop(s['uid'],None)
            with ledger.transaction():
                for key,value in [('pending',pending),('ready',ready),('instruments',instruments),('last_scan',last_scan)]:
                    ledger.save_feed(key,value)
            if now-last_status>=10000:
                last_status=now
                status=ledger.report(now)|dict(heartbeat_ms=now,started_ms=started,release=release,
                    first_forward_hour=first_hour,last_scan=last_scan,pending_retests=len(pending),
                    ready_candidates=len(ready),manual_entry_halt=(args.db.parent/'entries_disabled').exists())
                atomic_json(args.db.parent/'status.json',status)
            time.sleep(1)


if __name__=='__main__':
    main()
