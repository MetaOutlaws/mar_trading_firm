#!/usr/bin/env python3
"""Isolated public-only forward worker. Does not connect to the current broker."""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import fcntl
import json
import logging
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlencode


ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from research.cipher_forward.config import frozen_config
from research.cipher_forward.freeze import ExperimentVoid, entries_halted, freeze_before_warmup
from research.cipher_forward.seed import SeedStore, atomic_json
from research.cipher_forward.reporting import report_and_verify
from research.cipher_forward.pace import (
    FUNDED_CONCURRENCY, FUNDED_MIN_INTERVAL_S, SCAN_CONCURRENCY, SCAN_MIN_INTERVAL_S,
    SCAN_OFFSET_MS)
from research.cipher_forward.public import PublicClient
from research.cipher_forward.ledger import PaperTrial, BOOKS, MINUTE, canonical, fresh_quote, funding_known
from research.cipher_forward.feed import SignalFeed, advance_retest, HOUR
from research.cipher_forward.strategy import decision as cipher_decision
from research.cipher_forward.storage import (
    GuardAnnouncer, StorageWriteBlocked, assess_storage, disable_entries,
    ledger_nbytes, loud, storage_settings_from_env)

ALLOWED=frozenset(('instruments-info','kline','orderbook','funding/history'))
# skew_ms = now_ms - bybit_time, where negative means the local clock is behind Bybit.
# The SGP1 host runs a few tens of milliseconds behind Bybit, so a small negative
# skew is healthy. Further behind than MAX_NEGATIVE_SKEW_MS is a clock mismatch;
# a response older than MAX_STALE_MS (skew above that) is stale.
MAX_NEGATIVE_SKEW_MS=2000
MAX_STALE_MS=5000
logger=logging.getLogger(__name__)


def now_ms():
    return time.time_ns()//1_000_000


def bar_is_closed(close_ms, bybit_time_ms):
    """Whether a bar is closed and usable.

    Uses Bybit server time and the bar's own close timestamp. The local clock
    is not an argument. A bar whose close is after Bybit server time is still open.
    """
    return int(close_ms)<=int(bybit_time_ms)


def closed_bar_asof(bybit_time_ms, duration_ms):
    """Latest duration boundary Bybit server time has reached.

    Bar parsers keep a bar when its close is at or before this value, so a
    close after Bybit server time is left out. The local clock is not an argument.
    """
    server_ms=int(bybit_time_ms)
    step=int(duration_ms)
    if step<=0 or server_ms<0:
        raise ValueError('bybit time missing')
    boundary=server_ms//step*step
    # The boundary itself is a close timestamp. It is usable only when Bybit
    # has already reached it.
    if not bar_is_closed(boundary, server_ms):
        raise ValueError('bybit time missing')
    return boundary


def bybit_server_time(market, symbol='BTCUSDT'):
    """Fresh Bybit server time from an allowlisted public response.

    The value is the exchange ``time`` field, not the local clock and not
    local time minus skew_ms.
    """
    body=market.get('instruments-info', symbol=symbol)
    server_ms=market.bybit_time_ms
    if server_ms is None:
        server_ms=int(body['time'])
    return int(server_ms)


class Market:
    def __init__(self, interval=.2, concurrency=2):
        self.client=PublicClient(min_interval_s=interval,concurrency=concurrency,
                                 max_attempts=3,header_cap_s=30)
        # Last accepted Bybit server time. Closed-bar decisions read this, not now_ms.
        self.bybit_time_ms=None

    def get(self, path, **params):
        if path not in ALLOWED:
            raise ValueError('only allowlisted public market GETs are permitted')
        body=self.client.get('https://api.bybit.com/v5/market/'+path+'?'+
            urlencode(dict(category='linear',**params)),{'User-Agent':'MAR-cipher-forward-paper/1'})
        bybit_time=int(body['time'])
        # skew_ms = now_ms - bybit_time, where negative means the local clock is behind Bybit.
        skew_ms=now_ms()-bybit_time
        symbol=params.get('symbol','')
        # One skew line per response, so every scan that calls get logs skew.
        logger.info('bybit response symbol=%s skew_ms=%s',symbol,skew_ms)
        if skew_ms<-MAX_NEGATIVE_SKEW_MS:
            logger.warning(
                'bybit clock mismatch symbol=%s skew_ms=%s failed_bound=MAX_NEGATIVE_SKEW_MS limit=%s',
                symbol,skew_ms,-MAX_NEGATIVE_SKEW_MS)
            raise ValueError('stale response or clock mismatch')
        if skew_ms>MAX_STALE_MS:
            logger.warning(
                'bybit stale response symbol=%s skew_ms=%s failed_bound=MAX_STALE_MS limit=%s',
                symbol,skew_ms,MAX_STALE_MS)
            raise ValueError('stale response or clock mismatch')
        self.bybit_time_ms=bybit_time
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
    return dict(hour=asof,pending=pending,ready=ready,observations=observations,histories=histories,
                instruments=instruments,coverage=len(histories),universe=len(feed.universe),
                available=len(instruments),unavailable=sum(h.get('unavailable',False) for h in histories.values()))


def warmup(seed_root,context_root):
    # Hashes are durable before any seed, bar, or network call in this function.
    state_dir=Path(seed_root).parent
    frozen=freeze_before_warmup(state_dir, now_ms())
    if frozen.get('void'):
        raise ExperimentVoid(frozen.get('banner') or 'experiment void')
    config=frozen_config();asof=now_ms()//HOUR*HOUR
    seed=SeedStore(seed_root,config['universe'],initialize_asof=asof)
    market=Market(.15,6);feed=SignalFeed(market.get,config['universe'],context_root,seed_root)
    results=[]
    def prepare(symbol):
        rows=market.get('instruments-info',symbol=symbol)['result']['list']
        matches=[r for r in rows if r.get('symbol')==symbol and r.get('status')=='Trading']
        if not matches: return dict(symbol=symbol,unavailable=True,reason='instrument_not_trading')
        if len(matches)!=1: raise ValueError('duplicate instrument')
        # The seed anchor above is fixed before any response. Bars that are
        # fetched are closed on Bybit's clock, not on the local hour.
        server_asof=closed_bar_asof(market.bybit_time_ms, HOUR)
        bars=seed.advance(symbol,server_asof,market.get)
        # Evaluate only to establish a valid causal feature state. No fills,
        # trade paths, outcomes or optimization are calculated during warmup.
        state=cipher_decision(symbol,bars,seed.start,server_asof)
        context=feed.long_context(symbol,server_asof)
        return dict(symbol=symbol,ready=True,hours=len(bars)-1,
            cipher_signal_evaluated=True,l01_processed_through=context['processed_through'])
    with cf.ThreadPoolExecutor(max_workers=6) as pool:
        jobs={pool.submit(prepare,s):s for s in config['universe']}
        for job in cf.as_completed(jobs):
            try: value=job.result()
            except Exception as exc: value=dict(symbol=jobs[job],error=f'{type(exc).__name__}: {exc}')
            results.append(value)
            print(json.dumps(dict(completed=len(results),total=len(jobs),**value)),flush=True)
    failures=[r for r in results if 'error' in r]
    available=sum(r.get('ready',False) for r in results)
    if market.bybit_time_ms is not None:
        asof=closed_bar_asof(market.bybit_time_ms, HOUR)
    receipt=dict(ready=not failures and available>0,asof_ms=asof,available=available,
        failures=failures,instruments=sorted(results,key=lambda r:r['symbol']),seed=seed.receipt(),
        indicator_state_only=True,trades=0,signal_outcomes=0,performance_recorded=False,pnl=None)
    atomic_json(Path(seed_root).parent/'warmup.json',receipt)
    if not receipt['ready']: raise ValueError('warmup incomplete; see warmup.json; no simulated-portfolio reset')


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


def prune_quotes(quotes, positions, ready, now):
    """Keep quotes for open positions and signals still inside the entry minute."""
    open_symbols = {p['symbol'] for p in positions if p.get('status') == 'open'}
    due = {s['symbol'] for s in ready.values()
           if s['action_ms'] <= now < s['action_ms'] + MINUTE}
    keep = open_symbols | due
    return {symbol: quote for symbol, quote in quotes.items() if symbol in keep}


def storage_tick(ledger, db_path, storage, announcer, now, last_retention):
    """Measure the main paper volume and the ledger volume, then retain or halt.

    A low-space halt stops ledger writes. Entry disablement uses the same
    flag an operator can set by hand, and this function does not clear it.
    """
    decision=assess_storage(db_path, storage.main_paper_db,
        min_free_bytes=storage.min_free_bytes, ledger_max_bytes=storage.ledger_max_bytes)
    if decision.blocked:
        ledger.block_writes(decision.reason)
        announcer.announce(decision.reason, now)
        try: disable_entries(db_path.parent)
        except OSError as exc: loud(f'could not disable entries: {exc}')
        return decision
    # Retention is at most once a minute. Crossing the size cap between those
    # passes still halts immediately, without a vacuum on every quote tick.
    due=now-last_retention[0] >= 60_000
    if decision.over_size and not due:
        reason=(f'cipher-forward ledger is {decision.ledger_bytes} bytes, above the '
                f'{storage.ledger_max_bytes}-byte cap; stopping writes and disabling entries '
                f'to protect the main paper DB at {storage.main_paper_db}')
        ledger.block_writes(reason)
        announcer.announce(reason, now)
        try: disable_entries(db_path.parent)
        except OSError as exc: loud(f'could not disable entries: {exc}')
        return decision
    ledger.allow_writes()
    still_over=False
    if due or decision.over_size:
        still_over=ledger.enforce_retention(now, max_age_ms=storage.ledger_max_age_ms,
            max_bytes=storage.ledger_max_bytes, min_free_bytes=storage.min_free_bytes,
            main_free_bytes=decision.main_free_bytes)
        last_retention[0]=now
    if still_over:
        reason=(f'cipher-forward ledger is {ledger_nbytes(db_path)} bytes after retention, '
                f'above the {storage.ledger_max_bytes}-byte cap; stopping writes and disabling entries '
                f'to protect the main paper DB at {storage.main_paper_db}')
        ledger.block_writes(reason)
        announcer.announce(reason, now)
        try: disable_entries(db_path.parent)
        except OSError as exc: loud(f'could not disable entries: {exc}')
    return decision


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--db',type=Path,required=True)
    parser.add_argument('--seed-root',type=Path)
    parser.add_argument('--warmup',action='store_true')
    parser.add_argument('--verify',action='store_true')
    parser.add_argument('--context-root',type=Path,default=Path('/context'))
    parser.add_argument('--initialize',action='store_true')
    parser.add_argument('--audit',action='store_true')
    args=parser.parse_args()
    if os.environ.get('TRADING_MODE','paper').lower()!='paper' or os.environ.get('GO_LIVE_CONFIRMED'):
        raise ValueError('paper only')
    args.db.parent.mkdir(parents=True,exist_ok=True)
    lock=(args.db.parent/'worker.lock').open('a')
    if not args.audit and not args.verify:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    seed_root=args.seed_root or args.db.parent/'seed'
    storage=storage_settings_from_env()
    if args.warmup or args.initialize:
        decision=assess_storage(args.db, storage.main_paper_db,
            min_free_bytes=storage.min_free_bytes, ledger_max_bytes=storage.ledger_max_bytes)
        if decision.blocked:
            loud(decision.reason)
            try: disable_entries(args.db.parent)
            except OSError as exc: loud(f'could not disable entries: {exc}')
            raise SystemExit(3)
    if args.warmup:
        warmup(seed_root,args.context_root);return
    ledger=PaperTrial(args.db,frozen_config(),create=args.initialize)
    if args.verify:
        decision=assess_storage(args.db, storage.main_paper_db,
            min_free_bytes=storage.min_free_bytes, ledger_max_bytes=storage.ledger_max_bytes)
        if decision.blocked:
            loud(decision.reason)
            raise SystemExit(3)
        value=report_and_verify(ledger,now_ms(),args.db.parent,seed_root)
        print(json.dumps(value['verification'],indent=2))
        raise SystemExit(0 if value['verification']['activation_verified'] else 2)
    if args.initialize or args.audit:
        print(json.dumps(ledger.report(now_ms()),indent=2));return
    started=now_ms()
    release=(ROOT/'CIPHER_RELEASE_SHA').read_text().strip() if (ROOT/'CIPHER_RELEASE_SHA').is_file() else 'unpublished'
    announcer=GuardAnnouncer();last_retention=[-60_000]
    decision=storage_tick(ledger,args.db,storage,announcer,started,last_retention)
    first_hour=ledger.feed('first_forward_hour')
    if first_hour is None:
        warmup_path=args.db.parent/'warmup.json'
        if not warmup_path.is_file() or not json.loads(warmup_path.read_text()).get('ready'):
            raise ValueError('initial indicator preparation has not passed')
        first_hour=(started//HOUR+1)*HOUR
        if not ledger.writes_blocked:
            ledger.save_feed('first_forward_hour',first_hour)
    halted, guard = entries_halted(args.db.parent, started)
    pending=ledger.feed('pending',{});ready=ledger.feed('ready',{})
    instruments=ledger.feed('instruments',{})
    market=Market(SCAN_MIN_INTERVAL_S, SCAN_CONCURRENCY)
    funded_market=Market(FUNDED_MIN_INTERVAL_S, FUNDED_CONCURRENCY)
    opportunity_market=Market(.1,4)
    funding_market=Market(.25,2)
    # Indicator corruption must not disable exits for already-open positions.
    feed=None
    quotes={};settlements={};jobs={};busy=set();last_requested_hour=None
    retest_minute=None;retest_complete=None;last_quote={};last_funding={};last_status=0;last_cycle_tick=None;last_report=0
    last_scan=ledger.feed('last_scan',{})
    if not ledger.writes_blocked:
        ledger.observe(started,'startup',dict(release=release,first_forward_hour=first_hour,paper_only=True))
    with cf.ThreadPoolExecutor(max_workers=2) as work_pool, cf.ThreadPoolExecutor(max_workers=FUNDED_CONCURRENCY) as quote_pool, \
         cf.ThreadPoolExecutor(max_workers=4) as opportunity_pool, cf.ThreadPoolExecutor(max_workers=2) as funding_pool:
        while True:
            now=now_ms();minute=now//MINUTE*MINUTE;hour=now//HOUR*HOUR
            decision=storage_tick(ledger,args.db,storage,announcer,now,last_retention)
            halted, guard = entries_halted(args.db.parent, now)
            for job in list(jobs):
                if not job.done(): continue
                kind,key=jobs.pop(job);busy.discard((kind,key))
                if ledger.writes_blocked:
                    # Drop the result. Persisting it would keep filling the disk.
                    try: job.result()
                    except Exception: pass
                    continue
                try:
                    result=job.result()
                    if kind=='scan':
                        ledger.history_snapshot(result['hour'],result['histories'])
                        instruments.update(result['instruments'])
                        if result['hour']>=first_hour:
                            pending.update({p['uid']:p for p in result['pending']})
                            ready.update({s['uid']:s for s in result['ready']})
                            retest_minute=None
                        for observation in result['observations']:
                            ledger.observe(now,'scan',observation|dict(hour=result['hour']))
                        last_scan={k:result[k] for k in ('hour','coverage','universe','available','unavailable')}
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
            # The request still waits six minutes. The closed hour itself is
            # Bybit server time, not this local `hour`.
            if (hour!=last_requested_hour and now>=hour+SCAN_OFFSET_MS
                    and not any(k=='scan' for k,_ in busy)):
                last_requested_hour=hour
                try:
                    if feed is None:
                        feed=SignalFeed(market.get,ledger.config['universe'],args.context_root,seed_root)
                    scan_asof=closed_bar_asof(bybit_server_time(market), HOUR)
                    job=work_pool.submit(scan,feed,scan_asof);jobs[job]=('scan',scan_asof);busy.add(('scan',scan_asof))
                except Exception as exc:
                    ledger.observe(now,'feed_initialization_error',dict(error=str(exc)))
            if feed is not None and pending and retest_minute!=minute and not any(k=='retest' for k,_ in busy):
                # `minute` only rate-limits the poll. The as-of passed in is the
                # minute Bybit has closed, so a locally early clock cannot use
                # a bar whose close is still after server time.
                try:
                    retest_asof=closed_bar_asof(bybit_server_time(market), MINUTE)
                    retest_minute=minute;key=tuple(sorted(pending))
                    job=work_pool.submit(retests,feed,dict(pending),retest_asof)
                    jobs[job]=('retest',key);busy.add(('retest',key))
                except Exception as exc:
                    retest_minute=minute
                    ledger.observe(now,'retest_clock_error',dict(error=f'{type(exc).__name__}: {exc}'))
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
                if not ledger.writes_blocked and (batch or now//15000 != last_cycle_tick):
                    ledger.cycle(f'cycle:{now}',now,quotes,instruments,batch,settlements,
                                 manual_halt=halted)
                    last_cycle_tick=now//15000
            except StorageWriteBlocked as exc:
                ledger.block_writes(str(exc))
                announcer.announce(str(exc), now)
                try: disable_entries(args.db.parent)
                except OSError: pass
            except Exception as exc:
                # A ledger/input conflict must never be bypassed by subsequent
                # admissions. Keep supervision and exits running with the halt.
                (args.db.parent/'entries_disabled').touch(exist_ok=True)
                try:
                    ledger.observe(now,'cycle_error',dict(error=f'{type(exc).__name__}: {exc}'))
                    for s in batch:
                        ledger.observe(now,'quarantined_candidate',s)
                except StorageWriteBlocked:
                    announcer.announce(ledger.block_reason or 'ledger writes blocked', now)
                settlements.clear()
            for s in batch: ready.pop(s['uid'],None)
            quotes = prune_quotes(quotes, ledger.positions(), ready, now)
            if not ledger.writes_blocked:
                with ledger.transaction():
                    for key,value in [('pending',pending),('ready',ready),('instruments',instruments),('last_scan',last_scan)]:
                        ledger.save_feed(key,value)
            if now-last_status>=10000:
                last_status=now
                status=ledger.report(now)|dict(heartbeat_ms=now,started_ms=started,release=release,
                    first_forward_hour=first_hour,last_scan=last_scan,pending_retests=len(pending),
                    ready_candidates=len(ready),disk_free_bytes=decision.ledger_free_bytes,
                    main_paper_free_bytes=decision.main_free_bytes,
                    main_paper_db=str(storage.main_paper_db),
                    ledger_bytes=decision.ledger_bytes,
                    storage_writes_blocked=ledger.writes_blocked,
                    storage_guard=decision.reason,
                    manual_entry_halt=halted,
                    run_void=bool(guard.get('void')),
                    void_banner=guard.get('banner') or '')
                try: atomic_json(args.db.parent/'status.json',status)
                except OSError as exc: loud(f'could not write status.json: {exc}')
            if not ledger.writes_blocked and now-last_report>=60000:
                last_report=now
                try: report_and_verify(ledger,now,args.db.parent,seed_root)
                except StorageWriteBlocked:
                    announcer.announce(ledger.block_reason or 'ledger writes blocked', now)
                except Exception as exc:
                    try: ledger.observe(now,'report_error',dict(error=str(exc)))
                    except StorageWriteBlocked: pass
            time.sleep(.25)


if __name__=='__main__':
    # The worker otherwise has no logging config, so the skew line would be dropped.
    logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s %(message)s')
    main()
