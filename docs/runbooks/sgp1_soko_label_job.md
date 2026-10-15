# SGP1 Soko label job

Tsuro: this is the host job that writes `last_soko_trend.json` on SGP1 so
paper no longer waits on a DESKTOP push. It does not restart the paper
container, does not change `engine.py`, and does not touch
`config/approved_strategies.json`.

Paper already rereads `data/last_soko_trend.json` every cycle
(`core/data/soko_trend.py`). On this box that file is
`/data/state/data/last_soko_trend.json`. A host write shows up on the next
cycle with no reload.

The job fetches public Binance BTCUSDT 4h klines (`limit=60`), drops the
forming bar, and classifies the remaining closed bars with the same EMA20
slope / LH-LL rules as Soko's desktop script. It publishes:

```json
{"schema": "soko_trend_v1", "trend": "chop", "as_of": "2026-10-10T04:00:00Z", "source": "sgp1_auto"}
```

`trend` is `bull`, `bear`, or `chop`. `as_of` is the last closed bar's close
time plus 1 ms. Bybit is off. Parity is defined on Binance.

## Coexistence with DESKTOP

There is no in-repo HTTP push. DESKTOP/Soko keeps dropping the same file.
This writer replaces it only when its own `as_of` is strictly newer. An equal
timestamp, or an older one, is left byte-for-byte alone, including a desktop
file whose `source` is `soko`.

If this job cannot reach Binance it logs one error line, exits non-zero, and
does not touch the file. A file that is missing, unreadable, or has no
parseable `as_of` is replaced on the next successful classification: there is
no dated stamp to protect. PR #102's 6 hour fail-closed
(`SOKO_TREND_MAX_AGE_HOURS`, default 6, in `core/data/soko_trend.py`) sits
regime-gated sleeves out once that file goes stale. Nothing in this job
changes that gate.

## Install

Do this on the host, not inside the paper container. Python 3.9+ from the
OS is enough. There is no pip install.

1. Back up the live file before the first run:

```bash
sudo cp -a /data/state/data/last_soko_trend.json \
  /data/state/data/last_soko_trend.json.bak.$(date -u +%Y%m%dT%H%M%SZ)
```

2. Copy the script and the units from this checkout:

```bash
sudo install -d /usr/local/lib/sgp1
sudo install -m 0644 scripts/sgp1_soko_label_job.py \
  /usr/local/lib/sgp1/sgp1_soko_label_job.py
sudo install -m 0644 deploy/sgp1-soko-label.service \
  /etc/systemd/system/sgp1-soko-label.service
sudo install -m 0644 deploy/sgp1-soko-label.timer \
  /etc/systemd/system/sgp1-soko-label.timer
```

3. Load the units and enable the timer. Do not restart paper.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now sgp1-soko-label.timer
```

4. One manual run:

```bash
sudo systemctl start sgp1-soko-label.service
```

The timer itself fires at `HH:05:00` UTC (`OnCalendar=*-*-* *:05:00 UTC`),
which is the same minute the desktop log has been using. `Persistent=true`
runs one missed slot after a reboot. It does not replay every hour the host
was down.

`SOKO_TREND_PATH` in the unit is the destination. Change that line and
`daemon-reload` if the state mount is not `/data/state/data`. Do not point
it at a different filesystem from the directory it writes, or the rename
stops being atomic.

`SOKO_LABEL_BYBIT_FALLBACK=0` keeps Bybit off. Leave it that way.

## Verification

The service prints one JSON line per run. `status` `ok` and exit 0 means
classification finished. `written` true means this run published a newer
`as_of`. `written` false with `reason` `as_of_not_newer` means a desktop
file is tied or newer and was kept. That is still success.

```bash
systemctl show sgp1-soko-label.service -p ExecMainStatus -p Result --no-pager
journalctl -u sgp1-soko-label.service -n 1 --no-pager -o cat
python3 - << 'PY'
import json
path = "/data/state/data/last_soko_trend.json"
doc = json.load(open(path))
assert set(doc) == {"schema", "trend", "as_of", "source"}, doc
assert doc["schema"] == "soko_trend_v1"
assert doc["trend"] in {"bull", "bear", "chop"}
assert doc["source"] in {"sgp1_auto", "soko"}
print(doc)
PY
systemctl list-timers sgp1-soko-label.timer --no-pager
```

`source` stays `soko` when this run kept the desktop file. After the next
closed 4h bar, a later `as_of` from this job flips it to `sgp1_auto`.

A failed run looks like this: `ExecMainStatus` is not 0, the journal line
has `"status": "error"`, and the file's bytes match the backup you just took
(or the previous good file). Confirm with:

```bash
sudo cmp /data/state/data/last_soko_trend.json \
  /data/state/data/last_soko_trend.json.bak.<timestamp>
```

(`cmp` prints nothing when they match. Use the backup from the failed run's
window, not a later good copy.)

## Rollback

1. Stop the schedule. This does not restart paper.

```bash
sudo systemctl disable --now sgp1-soko-label.timer
```

2. Put the previous file back. Use the backup from the install step, or any
   earlier copy you trust. The reader wants a parseable `as_of`. If that
   stamp is older than 6 hours, regime-gated sleeves sit out until a fresh
   desktop push or until you turn this timer back on.

```bash
sudo cp -a /data/state/data/last_soko_trend.json.bak.<timestamp> \
  /data/state/data/last_soko_trend.json
python3 -c 'import json; print(json.load(open("/data/state/data/last_soko_trend.json")))'
```

3. Leave the unit files in place if you want them easy to re-enable.
   Removing them is optional:

```bash
sudo rm -f /etc/systemd/system/sgp1-soko-label.timer \
  /etc/systemd/system/sgp1-soko-label.service \
  /usr/local/lib/sgp1/sgp1_soko_label_job.py
sudo systemctl daemon-reload
```

Do not roll back by editing `engine.py` or the approval book. Neither file
is part of this job.
