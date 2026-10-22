#!/usr/bin/env python3
"""Read-only public funding download. Probe first; --download resumes month files."""
import argparse,csv,gzip,hashlib,io,json,math,time,urllib.parse,urllib.request
from datetime import datetime,timezone
from pathlib import Path
from collect_matched_history import BEGIN,END,HOST,SYMBOLS,month_bounds,month_labels

def validate(payload,symbol,lo,hi):
    if not isinstance(payload,dict) or payload.get('retCode')!=0:
        raise ValueError('API did not report retCode=0')
    result=payload.get('result',{})
    if result.get('category')!='linear' or not isinstance(result.get('list'),list):
        raise ValueError('Missing linear funding list')
    out=[];seen=set()
    for row in result['list']:
        if row.get('symbol')!=symbol:raise ValueError('Funding symbol mismatch')
        t=int(row['fundingRateTimestamp']);rate=str(row['fundingRate'])
        if not BEGIN<=t<END or not lo<=t<hi or t in seen:
            raise ValueError('Duplicate or out-of-window funding settlement')
        if not math.isfinite(float(rate)):raise ValueError('Nonfinite funding rate')
        out.append((t,rate));seen.add(t)
    return sorted(out)

def get_page(symbol,lo,hi,rawdir):
    params={'category':'linear','symbol':symbol,'startTime':lo,'endTime':hi-1,'limit':200}
    url=HOST+'/v5/market/funding/history?'+urllib.parse.urlencode(params)
    req=urllib.request.Request(url,headers={'User-Agent':'MAR-public-research-audit/1'})
    with urllib.request.urlopen(req,timeout=30) as response:
        data=response.read(2_000_001)
        if response.status!=200 or len(data)>2_000_000:raise ValueError('Unexpected HTTP response')
    try:payload=json.loads(data)
    except (json.JSONDecodeError,UnicodeDecodeError) as e:raise ValueError('Endpoint returned non-JSON') from e
    rows=validate(payload,symbol,lo,hi)
    rawdir.mkdir(parents=True,exist_ok=True)
    target=rawdir/f'{hi}.json.gz';temp=target.with_suffix('.partial')
    temp.write_bytes(gzip.compress(data,mtime=0));temp.replace(target)
    return rows,{'url':url,'requested_start':lo,'requested_end_exclusive':hi,'rows':len(rows),
                 'response_sha256':hashlib.sha256(data).hexdigest(),'raw_file':str(target),
                 'retrieved_at':datetime.now(timezone.utc).isoformat()}

def coverage(rows,lo,hi):
    ts=[t for t,rate in rows]
    if ts!=sorted(set(ts)) or any(t<lo or t>=hi for t in ts):raise ValueError('Invalid funding timestamps')
    intervals=[b-a for a,b in zip(ts,ts[1:])]
    return {'settlements':len(ts),'first':ts[0] if ts else None,'last':ts[-1] if ts else None,
            'min_interval_ms':min(intervals) if intervals else None,
            'max_interval_ms':max(intervals) if intervals else None,
            'matches_calendar_8h_grid':ts==list(range(lo,hi,8*60*60*1000)),
            'complete_verified':False}

def collect_month(out,symbol,month):
    lo,hi=month_bounds(month);folder=out/'funding'/symbol;folder.mkdir(parents=True,exist_ok=True)
    target=folder/(month+'.csv.gz');meta=folder/(month+'.json')
    if target.exists() and meta.exists():
        m=json.loads(meta.read_text())
        if m['symbol']!=symbol or m['month']!=month:raise ValueError('Resume identity mismatch')
        if hashlib.sha256(target.read_bytes()).hexdigest()!=m['sha256']:raise ValueError('Resume checksum mismatch')
        with gzip.open(target,'rt',newline='') as f:
            reader=csv.reader(f)
            if next(reader)!=['timestamp_ms','funding_rate']:raise ValueError('Resume schema mismatch')
            rows=[(int(t),rate) for t,rate in reader]
        if coverage(rows,lo,hi)!=m['coverage']:raise ValueError('Resume coverage mismatch')
        return m
    rows=[];requests=[];cursor=hi
    while cursor>lo:
        page,record=get_page(symbol,lo,cursor,out/'raw/funding'/symbol/month);requests.append(record)
        if not page:break
        rows.extend(page);cursor=page[0][0]
        time.sleep(.25)
    rows.sort();stats=coverage(rows,lo,hi)
    buf=io.StringIO(newline='');w=csv.writer(buf);w.writerow(['timestamp_ms','funding_rate']);w.writerows(rows)
    data=gzip.compress(buf.getvalue().encode(),mtime=0)
    temp=target.with_suffix('.partial');temp.write_bytes(data);temp.replace(target)
    m={'venue':'Bybit','category':'linear','symbol':symbol,'month':month,'coverage':stats,
       'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'requests':requests}
    tmp=meta.with_suffix('.partial');tmp.write_text(json.dumps(m,indent=2)+'\n');tmp.replace(meta)
    return m

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=Path('downloads'))
    p.add_argument('--from-month',default='2022-01');p.add_argument('--to-month',default='2025-12')
    p.add_argument('--download',action='store_true');args=p.parse_args()
    months=list(month_labels(args.from_month,args.to_month));out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    results=[];failure=None
    try:
        for month in months if args.download else months[:1]:
            for symbol in SYMBOLS:
                if args.download:
                    m=collect_month(out,symbol,month)
                    results.append({k:m[k] for k in ('symbol','month','coverage','sha256','bytes')})
                else:
                    lo,_=month_bounds(month);rows,record=get_page(symbol,lo,lo+24*60*60*1000,out/'probe/funding'/symbol)
                    results.append({'symbol':symbol,'probe_settlements':len(rows),**record})
                print(json.dumps(results[-1]),flush=True)
    except Exception as e:
        failure={'error_type':type(e).__name__,'message':str(e)};print(json.dumps(failure),flush=True)
    summary={'mode':'download' if args.download else 'probe','from_month':args.from_month,'to_month':args.to_month,
             'historical_2026_opened':False,'strategy_ready':False,'failure':failure,'results':results,
             'note':'Eight-hour grid is a diagnostic, not proof of actual historical funding schedule or completeness.'}
    (out/('FUNDING_DOWNLOAD_SUMMARY.json' if args.download else 'FUNDING_PROBE_SUMMARY.json')).write_text(json.dumps(summary,indent=2)+'\n')
    if failure:raise SystemExit(1)

if __name__=='__main__':main()
