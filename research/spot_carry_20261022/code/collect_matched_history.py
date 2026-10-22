#!/usr/bin/env python3
"""Public GET-only Bybit data collector. No credentials, orders or runtime changes.

Default: six 10-minute probes. --download: resume monthly 2022–2025 files.
No estimate of historical fee/margin rules is inferred from current API metadata.
"""
import argparse
import calendar
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

SYMBOLS = ('BTCUSDT', 'ETHUSDT')
STREAMS = {'spot': ('/v5/market/kline', 'spot'),
           'perpetual': ('/v5/market/kline', 'linear'),
           'mark': ('/v5/market/mark-price-kline', 'linear')}
HOST = 'https://api.bybit.com'
MINUTE = 60_000
BEGIN = 1640995200000
END = 1767225600000  # 2026-01-01 exclusive; no 2026 market outcomes.
HEADER = ('timestamp_ms', 'open', 'high', 'low', 'close', 'volume', 'turnover')

def validate_response(payload, category, symbol, lo, hi, mark=False):
    if not isinstance(payload, dict) or payload.get('retCode') != 0:
        raise ValueError('API did not report retCode=0')
    result = payload.get('result', {})
    if result.get('category') != category or result.get('symbol') != symbol:
        raise ValueError('Response instrument/category mismatch')
    raw = result.get('list')
    if not isinstance(raw, list):
        raise ValueError('Missing candle list')
    rows, seen = [], set()
    for x in raw:
        if not isinstance(x, list) or len(x) != (5 if mark else 7):
            raise ValueError('Unexpected candle field count')
        t = int(x[0])
        if t % MINUTE or not BEGIN <= t < END or not lo <= t < hi or t in seen:
            raise ValueError('Duplicate, unaligned or out-of-window candle')
        seen.add(t)
        o,h,l,c = map(float, x[1:5])
        if not all(math.isfinite(v) and v > 0 for v in (o,h,l,c)):
            raise ValueError('Nonpositive/nonfinite OHLC')
        if l > min(o,c) or h < max(o,c) or h < l:
            raise ValueError('Invalid OHLC bounds')
        if not mark:
            v,u = map(float,x[5:7])
            if not all(math.isfinite(z) and z >= 0 for z in (v,u)):
                raise ValueError('Invalid volume or turnover')
        rows.append([str(t)] + list(x[1:]) + (['',''] if mark else []))
    return sorted(rows,key=lambda x:int(x[0]))

def get_page(stream, symbol, lo, hi, rawdir):
    endpoint,category = STREAMS[stream]
    params = {'category':category,'symbol':symbol,'interval':'1',
              'start':lo,'end':hi-1,'limit':1000}
    url = HOST+endpoint+'?'+urllib.parse.urlencode(params)
    request = urllib.request.Request(url,headers={'User-Agent':'MAR-public-research-audit/1'})
    # Stop on unavailable/denied/rate-limited responses. Never rotate domains/proxies.
    with urllib.request.urlopen(request,timeout=30) as response:
        data = response.read(2_000_001)
        if len(data)>2_000_000:
            raise ValueError('Unexpectedly large response')
        if response.status != 200:
            raise ValueError('HTTP status is not 200')
    try:
        payload=json.loads(data)
    except (json.JSONDecodeError,UnicodeDecodeError) as e:
        raise ValueError('Endpoint returned non-JSON (possibly Site Unavailable)') from e
    rows=validate_response(payload,category,symbol,lo,hi,mark=stream=='mark')
    rawdir.mkdir(parents=True,exist_ok=True)
    target=rawdir/f'{lo}.json.gz'
    temp=target.with_suffix('.partial')
    temp.write_bytes(gzip.compress(data,mtime=0));temp.replace(target)
    return rows,{'url':url,'response_sha256':hashlib.sha256(data).hexdigest(),
                 'raw_file':str(target),'requested_start':lo,'requested_end_exclusive':hi,
                 'rows':len(rows),'retrieved_at':datetime.now(timezone.utc).isoformat()}

def month_bounds(label):
    dt=datetime.strptime(label,'%Y-%m').replace(tzinfo=timezone.utc)
    if not 2022<=dt.year<=2025:
        raise ValueError('Only 2022–2025 months are allowed')
    nxt=datetime(dt.year+(dt.month==12),dt.month%12+1,1,tzinfo=timezone.utc)
    return int(dt.timestamp()*1000),int(nxt.timestamp()*1000)

def month_labels(first,last):
    lo,_=month_bounds(first);_,end=month_bounds(last)
    if lo>=end:raise ValueError('Start is after end')
    while lo<end:
        label=datetime.fromtimestamp(lo/1000,timezone.utc).strftime('%Y-%m')
        yield label
        _,lo=month_bounds(label)

def validate_month(rows, lo, hi):
    times=[int(x[0]) for x in rows]
    if times != sorted(set(times)) or any(t<lo or t>=hi or t%MINUTE for t in times):
        raise ValueError('Month contains duplicate/out-of-window timestamps')
    expected=(hi-lo)//MINUTE
    missing=expected-len(times)
    return {'expected_minutes':expected,'observed_minutes':len(times),
            'missing_minutes':missing,'complete':missing==0}

def load_existing(target,meta,stream,symbol,month,lo,hi):
    m=json.loads(meta.read_text())
    if (m.get('stream'),m.get('symbol'),m.get('month'))!=(stream,symbol,month):
        raise ValueError('Resume metadata identity mismatch')
    if hashlib.sha256(target.read_bytes()).hexdigest()!=m['sha256']:
        raise ValueError('Resume file checksum mismatch; preserve and investigate')
    with gzip.open(target,'rt',newline='') as f:
        r=csv.reader(f)
        if tuple(next(r))!=HEADER:raise ValueError('Resume header mismatch')
        rows=list(r)
    stats=validate_month(rows,lo,hi)
    if stats!=m['coverage']:raise ValueError('Resume coverage mismatch')
    return m

def collect_month(out,stream,symbol,month):
    lo,hi=month_bounds(month)
    folder=out/stream/symbol;folder.mkdir(parents=True,exist_ok=True)
    target=folder/(month+'.csv.gz');meta=folder/(month+'.json')
    if target.exists() and meta.exists():
        return load_existing(target,meta,stream,symbol,month,lo,hi)
    rows=[];requests=[]
    for a in range(lo,hi,1000*MINUTE):
        b=min(a+1000*MINUTE,hi)
        batch,record=get_page(stream,symbol,a,b,out/'raw'/stream/symbol/month)
        rows.extend(batch);requests.append(record)
        time.sleep(.25)
    stats=validate_month(rows,lo,hi)
    buf=io.StringIO(newline='');w=csv.writer(buf);w.writerow(HEADER);w.writerows(rows)
    data=gzip.compress(buf.getvalue().encode(),mtime=0)
    temp=target.with_suffix('.partial');temp.write_bytes(data);temp.replace(target)
    m={'venue':'Bybit','stream':stream,'symbol':symbol,'month':month,
       'schema':'timestamp_ms,OHLC,base_volume,quote_turnover; mark has blank volume/turnover',
       'coverage':stats,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),
       'requests':requests,'historical_fees_margin_verified':False}
    mt=meta.with_suffix('.partial');mt.write_text(json.dumps(m,indent=2)+'\n');mt.replace(meta)
    return m

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('matched_carry_history_2022_2025'))
    parser.add_argument('--from-month',default='2022-01')
    parser.add_argument('--to-month',default='2025-12')
    parser.add_argument('--download',action='store_true')
    args=parser.parse_args();months=list(month_labels(args.from_month,args.to_month))
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    results=[];failed=None
    try:
        for month in months if args.download else months[:1]:
            for symbol in SYMBOLS:
                for stream in STREAMS:
                    if args.download:
                        m=collect_month(out,stream,symbol,month)
                        results.append({k:m[k] for k in ('stream','symbol','month','coverage','sha256','bytes')})
                        print(json.dumps(results[-1]),flush=True)
                    else:
                        lo,_=month_bounds(month)
                        rows,record=get_page(stream,symbol,lo,lo+10*MINUTE,out/'probe'/stream/symbol)
                        results.append({'stream':stream,'symbol':symbol,'rows':len(rows),**record})
                        print(json.dumps({'stream':stream,'symbol':symbol,'probe_rows':len(rows)}),flush=True)
    except Exception as e:
        failed={'error_type':type(e).__name__,'message':str(e)}
        print(json.dumps(failed),flush=True)
    summary={'completed_at':datetime.now(timezone.utc).isoformat(),'mode':'download' if args.download else 'probe',
             'from_month':args.from_month,'to_month':args.to_month,
             'historical_2026_opened':False,'results':results,'failure':failed,
             'strategy_ready':False,'remaining_requirements':['funding/mark reconciliation','historical cost evidence',
              'historical margin/collateral rules','matched coverage and basis audit','separately frozen strategy']}
    (out/('DOWNLOAD_SUMMARY.json' if args.download else 'PROBE_SUMMARY.json')).write_text(json.dumps(summary,indent=2)+'\n')
    if failed:raise SystemExit(1)

if __name__=='__main__':main()
