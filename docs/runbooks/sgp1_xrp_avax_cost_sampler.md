# SGP1 runbook: XRP/AVAX public cost sampler

Audience: Tsuro (ops). The job is a host process on SGP1 (`178.128.215.94`).
It is not installed by the change that added this page. Nothing below restarts
the paper stack. Do not merge-and-run; start it only when you mean to open the
7-day campaign.

## What it does

Reads public Bybit v5 market data for **XRPUSDT** and **AVAXUSDT** linear
perps. No API key.

Each snapshot is three GETs per symbol:

- `/v5/market/orderbook?category=linear&symbol=SYM&limit=50`
- `/v5/market/recent-trade?category=linear&symbol=SYM&limit=1000`
- `/v5/market/tickers?category=linear&symbol=SYM`

Cadence, UTC:

- one snapshot every 5 minutes
- from 2 minutes before until 3 minutes after each 4h candle open
  (00/04/08/12/16/20), one snapshot every 15 seconds

The first start plans its own end at **now + 168 hours** and stores that
instant in `sampler_run.json`. A reboot resumes until that same instant.
At the planned end it writes `COVERAGE.md` (missed bursts and gaps),
`SHA256SUMS`, and `SAMPLER_DONE`.

Default output directory: `/data/research/cost_sampler_xrp_avax/`.

Market data is daily-rotated gzip JSONL (`XRPUSDT_YYYYMMDD.jsonl.gz`).
Those files are capped at 2 GiB. Past the cap the process logs `SIZE_CAP`,
stops writing market data, and still exits cleanly at the planned end so the
manifests exist. A 7-day run at the desktop sample's size is on the order of
1 GB uncompressed and well under that cap once gzipped; the cap is the backstop.

Bybit's public HTTP budget is 600 requests per 5 seconds per IP. This job
allows itself at most 10 requests per 5 seconds and spaces calls by 250 ms
(a burst is 6 calls, about 0.4 requests/second). `10006` / HTTP 429 back off
from 5 s to 120 s.

## What it must not touch

- Docker, compose, or any container (`docker` / `docker compose` / `docker cp`
  / `docker exec`). Do not restart `mo-paper-paper-1` or the API container.
- `core/execution/engine.py` (the book of record on this branch starts
  `f275183b`; leave it unchanged).
- `config/approved_strategies.json`.
- Paper or live trading state: `firm.db`, `paper_cash.json`, `/data/state`,
  `.env`, keys.
- Do not put an API key in the unit, the script, or the environment. The
  sampler refuses an `--out` path that sits on the files above.

The 2026-10-09 desktop note recorded CloudFront **403** "configured to block
access from your country" from this box to both `api.bybit.com` and
`api.bytick.com`. The script rotates between those two public hosts and logs
`GEO_BLOCK`. It does not use a proxy, a VPN, or an authenticated endpoint.
If both hosts still 403, stop and report that. Do not work around it.

## Install

SSH to the box as you already do (the paper ops key). Run the commands **on
the host shell**, not inside a container.

```powershell
ssh -o ConnectTimeout=15 -i "$env:USERPROFILE\Downloads\mo-paper-vm-ops_id_ed25519" root@178.128.215.94
```

On the host:

```bash
python3 --version    # need 3.9 or newer; the script is stdlib only
id costsampler || sudo useradd --system --no-create-home --shell /usr/sbin/nologin costsampler

sudo install -d -o costsampler -g costsampler -m 0750 /data/research/cost_sampler_xrp_avax
sudo install -d -o root -g root -m 0755 /opt/cost-sampler

# Copy from the git checkout you just pulled. Do not copy from /app in a container.
sudo install -m 0755 scripts/xrp_avax_cost_sampler.py /opt/cost-sampler/xrp_avax_cost_sampler.py
sudo install -m 0644 docs/runbooks/sgp1_xrp_avax_cost_sampler.md /opt/cost-sampler/RUNBOOK.md
sudo install -m 0644 deploy/systemd/cost-sampler-xrp-avax.service /etc/systemd/system/cost-sampler-xrp-avax.service

sudo systemctl daemon-reload
sudo systemctl enable --now cost-sampler-xrp-avax.service
```

The unit runs as `costsampler`, not root. `ProtectHome=true` is set, so leave
the output under `/data/research/...` and do not move it into `/home`.

The unit does **not** pass `--hours`. The first start writes the 7-day end
into `sampler_run.json`. A later start (crash restart or reboot) keeps that
end. To pin a different end before the first start, use a drop-in and clear
the stock command:

```bash
sudo systemctl edit cost-sampler-xrp-avax
```

```ini
[Service]
ExecStart=
ExecStart=/usr/bin/python3 -u /opt/cost-sampler/xrp_avax_cost_sampler.py --out /data/research/cost_sampler_xrp_avax --max-bytes 2147483648 --end 2026-10-17T04:00:00Z
```

Then `sudo systemctl daemon-reload` and start. Do this only before the
campaign has written `sampler_run.json`, or the new `--end` replaces the plan.

## Verify

### First snapshot

The service shoots once as soon as it starts. Within a few seconds:

```bash
systemctl status cost-sampler-xrp-avax --no-pager
sudo -u costsampler ls -l /data/research/cost_sampler_xrp_avax
grep -E 'START|SNAP|GEO_BLOCK|REQ_FAIL|SIZE_CAP|API_ERR' /data/research/cost_sampler_xrp_avax/sampler.log | head
```

Healthy:

- `Active: active (running)` and not a container cgroup
- a `START` line with `symbols=XRPUSDT,AVAXUSDT` and an `end=` about 7 days out
- `SNAP regular5m ok=6/6` (2 symbols × 3 calls)
- `XRPUSDT_YYYYMMDD.jsonl.gz` and `AVAXUSDT_YYYYMMDD.jsonl.gz` owned by `costsampler`

Confirm the book depth and that the call was public:

```bash
sudo -u costsampler python3 - <<'PY'
import gzip, json
from pathlib import Path
root = Path("/data/research/cost_sampler_xrp_avax")
for symbol in ("XRPUSDT", "AVAXUSDT"):
    path = sorted(root.glob(symbol + "_*.jsonl.gz"))[-1]
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        rec = json.loads(handle.readline())
    book = rec["orderbook"]["response"]["result"]
    print(symbol, rec["kind"], "bids", len(book["b"]), "asks", len(book["a"]),
          "host", rec["orderbook"].get("host"))
PY
```

Expect `kind` `regular5m`, on the order of 50 bids and 50 asks, and a host of
`https://api.bybit.com` or `https://api.bytick.com`.

A one-shot probe that does **not** arm the 7-day plan (use it before
`enable`, or point it at a scratch directory):

```bash
sudo -u costsampler python3 /opt/cost-sampler/xrp_avax_cost_sampler.py \
  --once --out /data/research/cost_sampler_xrp_avax
```

Exit 0 prints `once_test ok=6/6`. `--once` does not write `SAMPLER_DONE`.

Failure you stop for:

- `GEO_BLOCK` on both hosts, or `ok=0/6` with HTTP 403. The box is still
  geo-blocked. `sudo systemctl disable --now cost-sampler-xrp-avax.service`
  and report the log lines. Do not add a proxy or a key.
- `SIZE_CAP` on the first snapshot. The disk or the cap is wrong; do not
  delete trading data to make room. Check `df -h /data` only.

`journalctl -u cost-sampler-xrp-avax -n 50 --no-pager` mirrors the same lines.

### Burst check

Print the next windows without calling Bybit:

```bash
python3 /opt/cost-sampler/xrp_avax_cost_sampler.py --print-schedule
```

Example shape (times will differ):

```text
now_utc=2026-10-10T05:10:00Z now_gst=2026-10-10T09:10:00 in_burst=no
bar_open_utc=2026-10-10T08:00:00Z bar_open_gst=2026-10-10T12:00:00 window_utc=2026-10-10T07:58:00Z..2026-10-10T08:03:00Z
```

GST is UTC+4. Stay on the host across one window (5 minutes: T−2 min through
T+3 min). Then:

```bash
grep 'SNAP burst4h' /data/research/cost_sampler_xrp_avax/sampler.log | tail -n 30
```

Healthy: about 20 lines (15 to 21 is normal; request time eats the last edge),
`ok=6/6`, timestamps about 15 seconds apart, covering that window. A line in
the same minute as the bar open is the check. Zero `burst4h` lines for a
window the process was up through is a miss; it will show as **MISSED** in
`COVERAGE.md` at the end. Do not restart the paper engine because a burst
was thin.

## Stop

`systemctl stop` is a pause. It writes `COVERAGE.md` and `SHA256SUMS` and does
**not** write `SAMPLER_DONE`. The next `systemctl start` continues until the
original planned end.

```bash
sudo systemctl stop cost-sampler-xrp-avax.service
tail -n 5 /data/research/cost_sampler_xrp_avax/sampler.log   # END reason=stopped
```

To end the campaign early so a reboot does not resume it:

```bash
sudo systemctl stop cost-sampler-xrp-avax.service
sudo -u costsampler touch /data/research/cost_sampler_xrp_avax/SAMPLER_DONE
```

The planned end does this itself (`END reason=end_time` plus `SAMPLER_DONE`).
After that, `systemctl status` shows the unit inactive and a start exits
immediately with `ALREADY_DONE`. `Restart=on-failure` does not revive a clean
exit.

## Uninstall

Leaves the samples in place. Does not remove `/data/research`, does not touch
containers, and does not edit the approval book.

```bash
sudo systemctl disable --now cost-sampler-xrp-avax.service
sudo rm -f /etc/systemd/system/cost-sampler-xrp-avax.service
sudo systemctl daemon-reload
sudo rm -f /opt/cost-sampler/xrp_avax_cost_sampler.py /opt/cost-sampler/RUNBOOK.md
```

Remove the user only after you have copied anything you still want and you are
sure nothing else runs as `costsampler`:

```bash
sudo userdel costsampler
```

Deleting the samples is a separate decision. It is not part of uninstall:

```bash
# sudo rm -rf /data/research/cost_sampler_xrp_avax
```

## Copying output to the box

The sampler already writes **on** the box, under
`/data/research/cost_sampler_xrp_avax/`. There is nothing to `docker cp`.
Do not copy these files into `/app`, onto `config/approved_strategies.json`,
or into the paper container.

Pull a copy to the workstation for the cost write-up (after `SAMPLER_DONE`,
or any time; checksums are refreshed on each clean stop and at the planned end):

```powershell
scp -o ConnectTimeout=15 -i "$env:USERPROFILE\Downloads\mo-paper-vm-ops_id_ed25519" -r root@178.128.215.94:/data/research/cost_sampler_xrp_avax "$env:USERPROFILE\Downloads\cost_sampler_xrp_avax"
```

On the workstation (Git Bash, WSL, or the host itself):

```bash
cd cost_sampler_xrp_avax
sha256sum -c SHA256SUMS
```

Every line should end `OK`. `COVERAGE.md` lists gaps over 6 minutes and any
4h open inside the run that has no `burst4h` shots (**MISSED**). Read that
before treating the sample as continuous. `SHA256SUMS` covers the data files,
the log, `COVERAGE.md`, and `SAMPLER_DONE`. It does not list itself.

If SGP1 is geo-blocked and a sample had to be taken on another machine, copy
it **onto** the box only into this directory, as `costsampler`, then check
the sums there. Still no container copy:

```powershell
scp -o ConnectTimeout=15 -i "$env:USERPROFILE\Downloads\mo-paper-vm-ops_id_ed25519" -r .\cost_sampler_xrp_avax\* root@178.128.215.94:/data/research/cost_sampler_xrp_avax/
```

```bash
sudo chown -R costsampler:costsampler /data/research/cost_sampler_xrp_avax
cd /data/research/cost_sampler_xrp_avax && sha256sum -c SHA256SUMS
```

A second campaign belongs in a new directory. Do not delete `SAMPLER_DONE`
in place to "restart" on top of a finished sample; the coverage window would
mix two runs.
