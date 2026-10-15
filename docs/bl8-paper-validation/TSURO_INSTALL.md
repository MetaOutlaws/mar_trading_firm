# Install the BL8 paper-limits release on the stopped observer

Brian approved sizing the isolated BL8 paper book with the hourly `PAPER_LIMITS` defaults: 1% equity risk per trade, 10% of equity per position, 50% gross exposure, 1x leverage, and a 5 USDT minimum that is rejected rather than rounded up. This note is how to put that pinned commit on the stopped `mar-bl8-shadow` service.

The observer stays on its own tree and database:

- code: `/opt/mar-bl8/releases/<40-character SHA>`
- state: `/data/state/bl8-paper`
- unit: `mar-bl8-shadow.service`

It reads public Bybit market data only. `live_authorized` stays false. The installer does not merge this branch, does not check out `/data/app`, and does not restart the hourly paper container.

## Pin

Use the full 40-character commit SHA from the owner handoff, which is the head of this pull request. A branch name is not a pin. Record the SHA before doing anything else and pass that same value to every command below.

## Before touching the unit

On `mo-paper-vm-sgp1`, as root:

```bash
hostname
docker inspect -f '{{.State.Running}} {{.State.StartedAt}}' mo-paper-paper-1
git -C /data/app rev-parse HEAD
systemctl is-active mar-bl8-shadow.service || true
systemctl show mar-bl8-shadow.service -p FragmentPath -p ActiveState -p UnitFileState --no-page
```

`mo-paper-paper-1` must stay `true`. The hourly HEAD you just printed must be the same value after this procedure. `mar-bl8-shadow.service` must not be `active`. If it is active, stop only that unit:

```bash
systemctl stop mar-bl8-shadow.service
systemctl is-active mar-bl8-shadow.service || true
docker inspect -f '{{.State.Running}}' mo-paper-paper-1
```

The second docker line must still print `true`.

## Fetch the pin without checking it out

```bash
sha='<40-character SHA>'
before=$(git -C /data/app rev-parse HEAD)
git -C /data/app fetch origin cursor/bl8-paper-position-sizing-c1b2
git -C /data/app cat-file -e "$sha^{commit}"
test "$(git -C /data/app rev-parse FETCH_HEAD)" = "$sha"
test "$(git -C /data/app rev-parse HEAD)" = "$before"
docker inspect -f '{{.State.Running}}' mo-paper-paper-1
```

Fetching the pull-request branch updates `FETCH_HEAD` only. It does not check out that commit, does not move the hourly HEAD, and does not restart a container. If either `test` fails, stop and report that before installing.

## Keep the previous BL8 book

This commit changes the sleeve config, so the ledger will refuse a database written by the 1 USDT sizing rule. That refusal is the rule-change guard. Preserve the old files and let the new release open a new `paper.db`. Do not delete the old database to make the audit pass.

```bash
state=/data/state/bl8-paper
if [ -e "$state/paper.db" ]; then
  dest="$state/preserved-$(date -u +%Y%m%dT%H%M%SZ)"
  mkdir -p "$dest"
  chmod 700 "$dest"
  for name in paper.db paper.db-wal paper.db-shm; do
    if [ -e "$state/$name" ]; then
      mv "$state/$name" "$dest/"
    fi
  done
  printf 'Preserved the previous BL8 book in %s\n' "$dest"
fi
```

Leave `entries_disabled` as you found it. Leave `status.json` in place; the new process replaces it after it is started.

## Install the release and leave the service stopped

Extract the installer from the pinned commit into a private directory outside `/data/app`, then run that extracted file. Do not run a copy that came from another checkout.

```bash
sha='<40-character SHA>'
work=$(mktemp -d /root/bl8-install-XXXXXX)
git -C /data/app archive "$sha" scripts/deploy_bl8_shadow.sh | tar -x -C "$work"
bash "$work/scripts/deploy_bl8_shadow.sh" "$sha"
```

The script checks the Singapore hostname, that the hourly container is still running and paper-only, the release hashes, and the BL8 unit tests. It writes `/opt/mar-bl8/releases/<sha>`, points `mar-bl8-shadow.service` at that release, enables the unit, and does not start it.

If the audit reports that the existing book refused the release, the old database is still on disk. Move it with the preserve commands above and run the installer again. Do not delete it.

Confirm the install without starting the observer:

```bash
sha='<40-character SHA>'
systemctl is-active mar-bl8-shadow.service || true
systemctl cat mar-bl8-shadow.service | grep -E 'WorkingDirectory|ExecStart'
test -f "/opt/mar-bl8/releases/$sha/BL8_RELEASE_SHA"
docker inspect -f '{{.State.Running}}' mo-paper-paper-1
git -C /data/app rev-parse HEAD
```

`is-active` prints `inactive`. `WorkingDirectory` and `ExecStart` contain `/opt/mar-bl8/releases/<sha>`. The docker line is still `true`. The hourly HEAD is unchanged.

## Start only when asked

```bash
systemctl start mar-bl8-shadow.service
systemctl is-active mar-bl8-shadow.service
```

After the first 96-symbol scan, run the verification command the installer printed. It looks like:

```bash
python3 /opt/mar-bl8/releases/<sha>/scripts/verify_bl8_paper.py \
  --db /data/state/bl8-paper/paper.db \
  --expected-commit <sha>
```

Save that JSON on the host. Also keep `systemctl status mar-bl8-shadow.service`, `journalctl -u mar-bl8-shadow.service -n 200 --no-pager`, and `/data/state/bl8-paper/status.json`. Send those back for reconciliation.

`status.json` reports `account_equity_usdt` on the isolated book. New entries use that equity with the hourly caps. A size under 5 USDT is stored as a rejected signal (`below_min_notional`) and is not bumped up to the minimum.

To pause new entries while exits continue, create `/data/state/bl8-paper/entries_disabled`. To stop supervision entirely, `systemctl stop mar-bl8-shadow.service`, and report the gap. Stopping that unit does not stop the hourly container.
