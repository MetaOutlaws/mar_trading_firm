"""Host-side BTC + Connors + low-efficiency cap switch for the individually bind-mounted cloud approval file.

Run through SSH with host python3, not docker exec. This module's main receives
the pinned code payload from the generated standalone installer. No financial
account, trading mode, risk setting, position is changed. Only the six exact original hourly entries are replaced.
"""
import base64
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile

PAPER = "mo-paper-paper-1"
API = "mo-paper-api-1"


def docker(*args, input=None):
    result = subprocess.run(["docker", *args], input=input, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(f"Docker command failed ({' '.join(args[:3])}): {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout


def inspect(names):
    return json.loads(docker("inspect", *names)) if names else []


def container_python(name, code):
    return docker("exec", "-i", name, "python", "-", input=code)


def parse_result(output):
    matches = [line[len("HOURLY_JSON="):] for line in output.splitlines() if line.startswith("HOURLY_JSON=")]
    if len(matches) != 1:
        raise RuntimeError("Missing unambiguous container preflight result")
    return json.loads(matches[0])


def require_paper(names):
    code = """import sys,json
sys.path.insert(0,'/app')
from config.settings import get_settings, TradingMode
if get_settings().trading_mode is not TradingMode.PAPER:
    raise RuntimeError('STOP: expected PAPER mode')
print('HOURLY_JSON='+json.dumps({'mode':'paper'}))
"""
    for name in names:
        if parse_result(container_python(name, code)) != {"mode": "paper"}:
            raise RuntimeError("Unexpected mode result")


def source_for_file_mount(paper, target):
    rows = [m for m in paper.get("Mounts", []) if m.get("Destination") == target]
    if len(rows) != 1 or rows[0].get("Type") != "bind" or rows[0].get("RW") is not True:
        raise RuntimeError("Expected one writable file bind mount; no configuration changed")
    source = Path(rows[0]["Source"]).resolve(strict=True)
    if not source.is_file() or os.path.ismount(source):
        raise RuntimeError("Approval source is not a replaceable regular host file")
    return source


def readers_of(source, running):
    readers = []
    for row in running:
        for mount in row.get("Mounts", []):
            if mount.get("Type") != "bind":
                continue
            parent = Path(mount["Source"]).resolve()
            if source == parent or (parent.is_dir() and source.is_relative_to(parent)):
                readers.append(row["Name"].lstrip("/")); break
    return set(readers)


def atomic_host_update(source, wanted, retired):
    """Merge only after container writers have stopped; keep metadata intact."""
    before = source.read_bytes()
    current = json.loads(before)
    if not isinstance(current, dict):
        raise RuntimeError("Existing approval book is not a JSON object")
    for key, value in wanted.items():
        if key in current and current[key] != value:
            raise RuntimeError("Conflicting existing hourly approval: " + key)
    for key, value in retired.items():
        if key in current and current[key] != value:
            raise RuntimeError("Different baseline record: " + key)
    for key,value in current.items():
        if not isinstance(value,dict): continue
        strategy=value.get("strategy",key.split(":")[0])
        if strategy.startswith("hourly_compression") and strategy not in {"hourly_compression_v1","hourly_compression_connors_v1","hourly_compression_btc_connors_v1","hourly_compression_btc_connors_loweff_v1"} and (value.get("approved") or value.get("paper_override")):
            raise RuntimeError("Another active hourly variant: " + key)
    after = (json.dumps({**{k:v for k,v in current.items() if k not in retired}, **wanted}, indent=2)+"\n").encode()
    if json.loads(after) == current:
        return {"changed": False, "preserved_records": len(current), "approval_sha256": hashlib.sha256(before).hexdigest()}
    metadata = source.stat()
    backup = source.with_name(source.name+".before-hourly-host-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    with backup.open("xb") as f:
        f.write(before); f.flush(); os.fsync(f.fileno())
    os.chmod(backup, stat.S_IMODE(metadata.st_mode)); os.chown(backup, metadata.st_uid, metadata.st_gid)
    fd, temporary = tempfile.mkstemp(prefix=".hourly-host-", dir=source.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(after); f.flush(); os.fsync(f.fileno())
        os.chmod(temporary, stat.S_IMODE(metadata.st_mode)); os.chown(temporary, metadata.st_uid, metadata.st_gid)
        if source.read_bytes() != before:
            raise RuntimeError("Host approval book changed during update; no replacement made")
        os.replace(temporary, source)
        directory = os.open(source.parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)
    if source.read_bytes() != after:
        raise RuntimeError("Host approval readback differs from intended update")
    return {"changed": True, "backup": str(backup), "preserved_records": len(current),
            "approval_sha256": hashlib.sha256(after).hexdigest()}


def stop_update_resume(consumers, update):
    """Always try to restore the containers that were running before repair."""
    attempted = []
    errors = []
    try:
        for name in [PAPER, API]:
            if name in consumers:
                attempted.append(name)
                docker("stop", "--time", "30", name)
        states = inspect(list(consumers))
        if any(row["State"]["Running"] for row in states):
            raise RuntimeError("A consumer remains running; approval update cancelled")
        return update()
    finally:
        for name in [API, PAPER]:
            if name in attempted:
                try: docker("start", name)
                except Exception as exc: errors.append(str(exc))
        if errors:
            raise RuntimeError("Container restart needs attention: " + "; ".join(errors))


def main(payload, critical, allowed_previous):
    running = inspect(docker("ps", "-q").split())
    by_name = {r["Name"].lstrip("/"): r for r in running}
    if PAPER not in by_name:
        raise RuntimeError("Paper engine must be running before this repair; no containers started")
    preflight = """import sys,json,hashlib,pathlib,base64
sys.path.insert(0,'/app')
root=pathlib.Path('/app')
from config.settings import get_settings,TradingMode
from config.universe import APPROVALS_PATH
if get_settings().trading_mode is not TradingMode.PAPER: raise RuntimeError('PAPER required')
"""
    preflight += "critical="+repr(critical)+"\npayload="+repr(payload)+"\nallowed_previous="+repr(allowed_previous)+"\n"
    preflight += """for name,expected in critical.items():
    if hashlib.sha256((root/name).read_bytes()).hexdigest()!=expected:
        raise RuntimeError('Runtime interface differs: '+name)
for name,encoded in payload.items():
    path=root/name;data=base64.b64decode(encoded)
    allowed={hashlib.sha256(data).hexdigest()} | set(allowed_previous.get(name, []))
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() not in allowed:
        raise RuntimeError('Existing different module: '+name)
# Provide exact parent approval helper in memory when this VM never installed Connors.
import types
for parent in ['scripts.enable_hourly_connors','scripts.enable_hourly_btc_connors']:
    filename=parent.replace('.','/')+'.py'
    if parent not in sys.modules:
        module=types.ModuleType(parent);module.__file__=str(root/filename)
        exec(compile(base64.b64decode(payload[filename]),module.__file__,'exec'),module.__dict__)
        sys.modules[parent]=module
ns={'__name__':'hourly_preflight','__file__':str(root/'scripts/enable_hourly_btc_connors_loweff.py')}
exec(compile(base64.b64decode(payload['scripts/enable_hourly_btc_connors_loweff.py']),ns['__file__'],'exec'),ns)
before=APPROVALS_PATH.resolve(strict=True).read_bytes()
ns['merged_book'](json.loads(before))
print('HOURLY_JSON='+json.dumps({'approval_path':str(APPROVALS_PATH.resolve()),'approval_sha256':hashlib.sha256(before).hexdigest(),'records':ns['desired_records'](),'retired':ns['retired_records']()}))
"""
    result = parse_result(container_python(PAPER, preflight))
    source = source_for_file_mount(by_name[PAPER], result["approval_path"])
    if hashlib.sha256(source.read_bytes()).hexdigest() != result["approval_sha256"]:
        raise RuntimeError("Host and container do not see the same approval version")
    consumers = readers_of(source, running)
    if PAPER not in consumers or not consumers <= {PAPER, API}:
        raise RuntimeError("Unexpected approval consumers: " + repr(sorted(consumers)))
    require_paper(consumers)
    # Validate every running consumer before any module or approval mutation.
    for name in consumers - {PAPER}:
        other = parse_result(container_python(name, preflight))
        if other != result: raise RuntimeError("Consumer preflight differs: " + name)
    # New modules only; original rule remains for open position supervision.
    install = "import pathlib,base64,os,tempfile\nroot=pathlib.Path('/app')\npayload="+repr(payload)+"\n"
    install += """for name,encoded in payload.items():
    path=root/name;data=base64.b64decode(encoded)
    if path.exists() and path.read_bytes()==data: continue
    if path.exists():
        backup=path.with_name(path.name+'.before-btc-connors-loweff-'+__import__('datetime').datetime.now(__import__('datetime').timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        backup.write_bytes(path.read_bytes())
    fd,temp=tempfile.mkstemp(prefix='.hourly-repair-',dir=path.parent)
    with os.fdopen(fd,'wb') as handle: handle.write(data);handle.flush();os.fsync(handle.fileno())
    os.chmod(temp,0o644);os.replace(temp,path)
print('Code update prepared')
"""
    with source.with_name(".hourly-compression-repair.lock").open("a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        for name in sorted(consumers): container_python(name, install)
        print("PAPER mode verified. Updating host approval file with readers stopped briefly.", flush=True)
        changed = stop_update_resume(consumers, lambda: atomic_host_update(source, result["records"], result["retired"]))
    after = inspect(list(consumers))
    if any(not r["State"]["Running"] for r in after):
        raise RuntimeError("An original consumer did not resume; inspect container status")
    # New container namespaces must resolve the replaced host file's new inode.
    readback = "import pathlib,hashlib\nprint('HOURLY_JSON='+__import__('json').dumps({'sha':hashlib.sha256(pathlib.Path("+repr(result['approval_path'])+").read_bytes()).hexdigest()}))\n"
    expected = hashlib.sha256(source.read_bytes()).hexdigest()
    for name in consumers:
        if parse_result(container_python(name, readback))["sha"] != expected:
            raise RuntimeError("Container still sees old approval bytes: " + name)
    final = docker("exec", PAPER, "python", "/app/scripts/enable_hourly_btc_connors_loweff.py", "--apply")
    print(json.dumps({"host_update": changed, "resumed": sorted(consumers)}, indent=2))
    print(final.strip())
    print("Next: verify a fresh completed scan; installed_awaiting_cycle is not scanning confirmation.")
