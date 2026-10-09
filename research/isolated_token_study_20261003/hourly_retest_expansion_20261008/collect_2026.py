"""Fixed 2026 replication acquisition plus 2025-Q4 warm-up. Never scores outcomes.
Derived from the original approved collector; selection/ranking rules unchanged.
Standard library only; no trading credentials. See NEXT_STAGES_20261009.md.
"""
import argparse
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import statistics
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

UTC = dt.timezone.utc
BEGIN = dt.datetime(2025, 10, 1, tzinfo=UTC)
END = dt.datetime(2026, 10, 1, tzinfo=UTC)
MINUTE, DAY = 60_000, 86_400_000
REFERENCE = {'BTCUSDT','ETHUSDT','SOLUSDT'}
EXCLUDE_BASE = {'USDT','USDC','DAI','TUSD','FDUSD','USDD','USDE','USD1','XAUT','PAXG'}
HOST = 'https://api.bybit.com'

def millis(x): return int(x.timestamp()*1000)
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write_json(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name+'.tmp')
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True))
    tmp.replace(p)
def safe_symbol(s):
    if not s or not all(c.isascii() and (c.isalnum() or c in '_-') for c in s):
        raise ValueError('Invalid symbol identifier')
    return s

class PublicAPI:
    def __init__(self, root, pause=.20):
        self.root = root; self.pause = pause
        self.raw = root/'raw'; self.raw.mkdir(parents=True, exist_ok=True)
    def get(self, endpoint, **params):
        assert endpoint in {'time','instruments-info','kline','funding/history'}
        query = urllib.parse.urlencode(sorted(params.items()))
        identity = endpoint+'?'+query
        key = hashlib.sha256(identity.encode()).hexdigest()
        path = self.raw/(key+'.json.gz')
        if path.exists():
            with gzip.open(path,'rt') as f: cached=json.load(f)
            assert cached['request']==identity
            return cached['response']
        if shutil.disk_usage(self.root).free < 5*1024**3:
            raise RuntimeError('Less than 5 GiB free; stopping new downloads to protect server disk')
        error = None
        for attempt in range(4):
            try:
                req=urllib.request.Request(HOST+'/v5/market/'+identity, headers={'User-Agent':'MAR-research-public-data/1.0'})
                with urllib.request.urlopen(req,timeout=30) as res:
                    data=res.read(); obj=json.loads(data)
                if obj.get('retCode') != 0:
                    raise RuntimeError(f"retCode={obj.get('retCode')}: {obj.get('retMsg')}")
                tmp=path.with_name(path.name+'.tmp')
                with gzip.open(tmp,'wt') as f: json.dump({'request':identity,'retrieved_at':dt.datetime.now(UTC).isoformat(),'response':obj},f)
                tmp.replace(path); time.sleep(self.pause)
                return obj
            except (json.JSONDecodeError,UnicodeDecodeError) as exc:
                error={'request':identity,'error':'Non-JSON response; public API inaccessible','response_prefix':data[:200].decode(errors='replace')}
                break
            except urllib.error.HTTPError as exc:
                error={'request':identity,'error':f'HTTP {exc.code}'}
                if exc.code in (400,401,403,404,451): break
            except Exception as exc:
                error={'request':identity,'error':str(exc)}
            time.sleep(min(2**attempt,8))
        write_json(self.root/'errors'/(key+'.json'),error)
        raise RuntimeError(error['error'])

def catalog(api, registry=None):
    path=api.root/'catalog.json'
    if path.exists(): return json.loads(path.read_text())
    records={}; errors=[]; status_counts={}
    for status in ['Trading','PendingOpen','PreLaunch','Settling','Delivering','Closed']:
        cursor=''; seen=set(); count=0
        while True:
            params=dict(category='linear',status=status,limit=1000)
            if cursor: params['cursor']=cursor
            try: payload=api.get('instruments-info',**params)['result']
            except Exception as exc:
                errors.append({'status':status,'error':str(exc)}); break
            for r in payload['list']:
                symbol=safe_symbol(r['symbol']); records[symbol]=r; count+=1
            cursor=payload.get('nextPageCursor','')
            if not cursor: break
            if cursor in seen: raise RuntimeError('Repeated instrument cursor')
            seen.add(cursor)
        status_counts[status]=count
    if registry:
        # Optional additive historical records; their provenance is preserved.
        extra=json.loads(registry.read_text())
        for r in extra['instruments']: records.setdefault(safe_symbol(r['symbol']),r)
        write_json(api.root/'historical_registry_supplied.json',extra)
    result=dict(instruments=list(records.values()),errors=errors,status_counts=status_counts,
                historical_universe_complete=False,classification_history_verified=False,
                note='Current API plus any supplied registry. Completeness requires independent historical audit.')
    write_json(path,result)
    if not records: raise RuntimeError('No catalog records; acquisition cannot continue')
    return result

def candles(api, symbol, interval, start, end):
    """Return complete interval opens in [start,end), never reach the exclusive replication endpoint."""
    assert end<=millis(END)
    step=DAY if interval=='D' else MINUTE
    rows={}; cursor=start
    while cursor<end:
        last=min(cursor+1000*step,end)
        response=api.get('kline',category='linear',symbol=symbol,interval=interval,start=cursor,end=last-1,limit=1000)
        for r in response['result']['list']:
            stamp=int(r[0])
            if not cursor<=stamp<last: raise ValueError('Candle outside requested window')
            if len(r)<7: raise ValueError('Incomplete candle schema')
            r=[stamp]+[float(x) for x in r[1:7]]
            if stamp%step or not all(math.isfinite(x) for x in r[1:]): raise ValueError('Invalid candle time/value')
            if min(r[1:5])<=0 or min(r[5:])<0 or r[2]<max(r[1],r[3],r[4]) or r[3]>min(r[1],r[2],r[4]):
                raise ValueError('Invalid OHLCV/turnover')
            if stamp in rows and rows[stamp]!=r: raise ValueError('Conflicting duplicate candle')
            rows[stamp]=r
        cursor=last
    return [rows[k] for k in sorted(rows)]

def write_csv(path,rows,header):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    with gzip.open(tmp,'wt',newline='') as f:
        w=csv.writer(f);w.writerow(header);w.writerows(rows)
    tmp.replace(path)
def read_csv(path):
    with gzip.open(path,'rt',newline='') as f: return list(csv.DictReader(f))
HEADER=['timestamp_ms','open','high','low','close','volume','turnover']

def calendar_months(start, end):
    current=start.replace(day=1)
    while current<end:
        yield current
        current=(current.replace(day=28)+dt.timedelta(days=4)).replace(day=1)

def month_starts():
    return calendar_months(dt.datetime(2026,1,1,tzinfo=UTC),END)

def acquisition_month_starts():
    return calendar_months(BEGIN,END)

def choose_months(instruments,daily):
    chosen=[]; ranks=[]
    for month in month_starts():
        ts=millis(month); candidates=[]
        for item in instruments:
            symbol=item['symbol']
            if symbol in REFERENCE: continue
            records=daily.get(symbol,{})
            if not records: continue
            launch=max(int(item.get('launchTime') or 0), min(records))
            delivery=int(item.get('deliveryTime') or 0)
            if ts-launch<90*DAY or (delivery and ts>=delivery): continue
            window=[records.get(ts-i*DAY) for i in range(1,31)]
            if any(x is None for x in window): continue
            median=statistics.median(window)
            if median<10_000_000: continue
            candidates.append((symbol,median))
        candidates.sort(key=lambda p:(-p[1],p[0]))
        for rank,(symbol,median) in enumerate(candidates,1):
            rec=dict(month=month.strftime('%Y-%m'),symbol=symbol,rank=rank,prior_30d_median_turnover=median,selected=rank<=15)
            ranks.append(rec)
            if rank<=15: chosen.append(rec)
    return chosen,ranks

def collect(root,registry=None):
    root.mkdir(parents=True,exist_ok=True)
    state_path=root/'STATUS.json'
    state=dict(status='starting',experiment_id='H-RETEST-EXPANSION-2026-01',scores_2026=False,acquires_reserved_2026=True,trade_outcomes_scored=False,trading_changes=False,errors=[])
    write_json(state_path,state)
    api=PublicAPI(root)
    try:
        api.get('time')
        info=catalog(api,registry)
        eligible=[]; exclusions=[]; daily={}
        for item in info['instruments']:
            symbol=item['symbol']
            ok=item.get('contractType')=='LinearPerpetual' and item.get('quoteCoin')=='USDT' and item.get('settleCoin')=='USDT'
            reason=None
            if not ok: reason='not USDT-settled linear perpetual'
            elif item.get('baseCoin') in EXCLUDE_BASE: reason='frozen stablecoin/metal exclusion'
            elif item.get('symbolType') not in ('',None): reason='nonempty symbolType requires crypto classification review'
            elif int(item.get('launchTime') or 0)>=millis(END): reason='launched after acquisition period'
            if reason:
                exclusions.append(dict(symbol=symbol,reason=reason)); continue
            eligible.append(item)
            path=root/'daily'/(symbol+'.csv.gz')
            try:
                if not path.exists():
                    start=max(millis(BEGIN),int(item.get('launchTime') or 0)//DAY*DAY)
                    delivery=int(item.get('deliveryTime') or 0)
                    end=min(millis(END),delivery) if delivery else millis(END)
                    write_csv(path,candles(api,symbol,'D',start,end),HEADER)
                daily[symbol]={int(r['timestamp_ms']):float(r['turnover']) for r in read_csv(path)}
            except Exception as exc: state['errors'].append(dict(symbol=symbol,stage='daily',error=str(exc)))
            state.update(status='daily_inventory',daily_symbols=len(daily))
            write_json(state_path,state)
            print('DAILY',symbol,len(daily.get(symbol,{})),flush=True)
        write_json(root/'catalog_exclusions.json',exclusions)
        chosen,ranks=choose_months(eligible,daily)
        write_json(root/'membership.json',chosen);write_json(root/'all_eligibility_ranks.json',ranks)
        write_json(root/'universe_freeze.json',dict(frozen_at=dt.datetime.now(UTC).isoformat(),
            membership_sha256=digest(root/'membership.json'),catalog_sha256=digest(root/'catalog.json'),
            daily_sha256={p.name:digest(p) for p in sorted((root/'daily').glob('*.csv.gz'))},
            historical_universe_complete=False,classification_history_verified=False,
            data_errors_before_outcomes=list(state['errors']),selected_union=sorted({x['symbol'] for x in chosen})))
        selected={x['symbol'] for x in chosen}|REFERENCE
        mapping={x['symbol']:x for x in eligible}
        for symbol in sorted(selected):
            item=mapping.get(symbol)
            if item is None:
                state['errors'].append(dict(symbol=symbol,stage='minutes',error='Selected/reference symbol absent from catalog'));continue
            start=max(millis(BEGIN),int(item.get('launchTime') or 0))
            start=((start+MINUTE-1)//MINUTE)*MINUTE
            delivery=int(item.get('deliveryTime') or 0)
            end=min(millis(END),delivery) if delivery else millis(END)
            try:
                for month in acquisition_month_starts():
                    following=(month.replace(day=28)+dt.timedelta(days=4)).replace(day=1)
                    a=max(start,millis(month));z=min(end,millis(following))
                    if a>=z: continue
                    path=root/'minutes'/symbol/(month.strftime('%Y-%m')+'.csv.gz')
                    if not path.exists(): write_csv(path,candles(api,symbol,'1',a,z),HEADER)
                    print('MINUTES',symbol,month.strftime('%Y-%m'),flush=True)
                funding=root/'funding'/(symbol+'.csv.gz')
                if not funding.exists():
                    # Include a settlement exactly at the terminal mark. No
                    # later price bars or post-boundary funding are requested.
                    records={};cursor=end
                    while cursor>=start:
                        rows=api.get('funding/history',category='linear',symbol=symbol,startTime=start,endTime=cursor,limit=200)['result']['list']
                        if not rows: break
                        for row in rows:
                            stamp=int(row['fundingRateTimestamp']);value=float(row['fundingRate'])
                            if not start<=stamp<=cursor or not math.isfinite(value): raise ValueError('Invalid funding timestamp/value')
                            if stamp in records and records[stamp]!=value: raise ValueError('Conflicting funding duplicate')
                            records[stamp]=value
                        next_cursor=min(int(r['fundingRateTimestamp']) for r in rows)-1
                        if next_cursor>=cursor: raise ValueError('Funding pagination made no progress')
                        cursor=next_cursor
                    write_csv(funding,sorted(records.items()),['timestamp_ms','funding_rate'])
            except Exception as exc: state['errors'].append(dict(symbol=symbol,stage='minutes_or_funding',error=str(exc)))
            state.update(status='minute_acquisition',last_symbol=symbol,selected_union_count=len(selected)-3)
            write_json(state_path,state)
        state.update(status='acquired_needs_audit' if not state['errors'] else 'partial_needs_audit',
            historical_universe_complete=False,historical_funding_schedule_verified=False,
            files={str(p.relative_to(root)):digest(p) for p in root.rglob('*') if p.is_file() and p.name not in {'STATUS.json','FILES_SHA256.json'} and p.suffix!='.tmp'})
        write_json(root/'FILES_SHA256.json',state.pop('files'))
        write_json(state_path,state)
    except Exception as exc:
        state.update(status='blocked',blocker=str(exc));write_json(state_path,state);raise

def archive(root,destination):
    if destination.exists(): raise FileExistsError('Refusing to replace an existing export')
    total=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    if shutil.disk_usage(destination.parent).free < total+1024**3:
        raise RuntimeError('Insufficient free space for a safe export; collected data is retained')
    with zipfile.ZipFile(destination,'x',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
        for p in sorted(root.rglob('*')):
            if p.is_file() and p.suffix!='.tmp': z.write(p,str(p.relative_to(root)))
    print(json.dumps(dict(archive=str(destination),bytes=destination.stat().st_size,sha256=digest(destination)),indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--historical-registry',type=Path)
    p.add_argument('--archive',type=Path)
    args=p.parse_args()
    collect(args.out,args.historical_registry)
    if args.archive: archive(args.out,args.archive)
