"""Migrate only the reviewed L01 execution-config marker. Default: dry run.

Run with the trading worker stopped, through the existing API container.
Does not restart workers, change cash/positions or claim runtime activation.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from config.settings import TradingMode, get_settings
from core.strategy.f111_config import L01_CONFIG_PATH, L01_ENABLE_PATH, load_f111_config

REVIEWED_OLD_SHA = "07c6427e07b0bd1a757c735151391a494c447d346ac27f7c98c0e4d4e42c13fb"


def migrate(path: Path, digest: str, *, apply: bool = False) -> dict:
    raw = path.read_bytes()
    old = json.loads(raw)
    if old.get("paper_only") is not True or old.get("approved_case") != "L01":
        raise RuntimeError("Expected the existing approved paper L01 marker")
    if old.get("configuration_sha256") == digest:
        return {"status": "already_current", "configuration_sha256": digest, "activation_verified": False}
    if old.get("configuration_sha256") != REVIEWED_OLD_SHA:
        raise RuntimeError("Marker differs from the reviewed deployment; inspect before upgrading")
    if apply:
        backup = path.with_name(path.name + ".execution-v1-backup")
        if backup.exists():
            if backup.read_bytes() != raw:
                raise RuntimeError("Existing marker backup differs; refusing overwrite")
        else:
            with backup.open("xb") as handle:
                handle.write(raw);handle.flush();os.fsync(handle.fileno())
        body = dict(old, configuration_sha256=digest, previous_configuration_sha256=REVIEWED_OLD_SHA,
                    execution_model_version="f111-forward-quote-v2", activation_verified=False,
                    recorded_at=datetime.now(timezone.utc).isoformat())
        fd, temporary = tempfile.mkstemp(prefix=".l01-execution-",dir=path.parent)
        try:
            with os.fdopen(fd,"w") as handle:
                json.dump(body,handle,indent=2);handle.write("\n");handle.flush();os.fsync(handle.fileno())
            if path.read_bytes() != raw:
                raise RuntimeError("Marker changed during migration")
            os.replace(temporary,path)
        finally:
            if os.path.exists(temporary):os.unlink(temporary)
    return {"status":"marker_migrated_restart_required" if apply else "dry_run",
            "configuration_sha256":digest,"activation_verified":False,"worker_started":False}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    settings=get_settings()
    if settings.trading_mode is not TradingMode.PAPER or settings.go_live_confirmed:
        raise RuntimeError('Execution migration requires unarmed paper settings')
    config,digest=load_f111_config(L01_CONFIG_PATH)
    if config.get('execution_model_version')!='f111-forward-quote-v2':
        raise RuntimeError('Expected reviewed execution version v2')
    print(json.dumps(migrate(L01_ENABLE_PATH,digest,apply=args.apply),indent=2))


if __name__=='__main__':main()
