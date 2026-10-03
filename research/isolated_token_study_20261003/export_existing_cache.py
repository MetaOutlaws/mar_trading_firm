"""Read existing BTC/ETH/SOL caches only; produce a new ZIP; never fetch or trade."""
import argparse, hashlib, json, zipfile
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--cache',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
files=[]
for sym in ('BTCUSDT','ETHUSDT','SOLUSDT'):
    for tf in ('1m','5m','15m','1h','4h'):
        f=a.cache/f'{sym}_{tf}.parquet'
        if f.is_file(): files.append(f)
    f=a.cache/'funding'/f'{sym}_funding.parquet'
    if f.is_file(): files.append(f)
if not files: raise SystemExit('No matching existing caches. No archive created.')
manifest=[]
with zipfile.ZipFile(a.output,'x',zipfile.ZIP_DEFLATED) as z:
    for f in files:
        before=f.stat()
        data=f.read_bytes()
        after=f.stat()
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
            raise RuntimeError(f'Cache changed during read; discard archive: {f.name}')
        name=str(f.relative_to(a.cache))
        z.writestr(name,data)
        manifest.append({'file':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    z.writestr('export_manifest.json',json.dumps(manifest,indent=2))
print(json.dumps({'archive':str(a.output),'files':len(files)},indent=2))
