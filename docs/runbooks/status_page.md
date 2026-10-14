# SGP1 status page

A read-only page a remote box can poll over HTTPS. Outbound SSH from that
box is blocked; 443 is not.

The page is its own process. On the SGP1 paper host it is also its own
compose project (`sgp1-status`), separate from the `mo-paper` project in
`/opt/mo-paper`. Deploying it, rotating its token, or rolling it back does
not restart the paper worker and does not reload the desk API.

Nothing on this page places an order. The process opens the book read-only,
replays `paper_cash.json` in memory, and reads the scan log, the Soko file,
the pid file, and the paper log. It does not import `scripts/run_paper_trading`.

## What it shows

`GET /` is HTML. `GET /api/status` is the same document as JSON.

- Health (database readable, worker process alive).
- Cash from the paper journal, and the latest equity snapshot.
- Open positions.
- Recent closed trades, including `strategy_label`, `sleeve`, and
  `strategy_version` from the blotter (#119).
- The last scan-summary card (#115 / #116), from `data/scan_summaries.jsonl`.
- Regime from `data/last_soko_trend.json`.
- HEAD (`GIT_SHA`) and `DEPLOYED_SHA` (`/app/data/DEPLOYED_SHA`), both.
- Worker pid, uptime, last cycle time (`data/last_cycle.json`), and recent
  errors from that file plus `logs/paper_trading.log`.

## Server environment

Set these in the server env file. On SGP1 that file is `/data/env/.env`.
The status process reads `STATUS_*` itself (`api/status_auth.py`). Those
names are not fields on `config/settings.py`. A blank `STATUS_PAGE_TOKEN`
disables the page: every request gets 503 and the book is not read.

| Variable | Purpose |
|---|---|
| `STATUS_PAGE_TOKEN` | Bearer token, and the password for Basic auth. Required. |
| `STATUS_PAGE_HOST` | Bind address. Default `127.0.0.1`. Compose sets `0.0.0.0` inside the status container only. |
| `STATUS_PAGE_PORT` | Default `8088`. Not published on the host. |
| `STATUS_PAGE_RATE_LIMIT` | Requests per IP per window. Default 30. |
| `STATUS_PAGE_RATE_WINDOW_SECONDS` | Window length. Default 60. |
| `STATUS_PAGE_DOMAIN` | Public DNS name. Set it for Let's Encrypt. Blank means a self-signed cert. |
| `STATUS_TLS_EMAIL` | Let's Encrypt account email. Used only when the domain is set. |
| `STATUS_TLS_SAN` | Subject alternative names for the self-signed cert. The local override defaults to `DNS:localhost,IP:127.0.0.1`. The SGP1 compose file sets `DNS:localhost,IP:127.0.0.1,IP:178.128.215.94`. |
| `STATUS_STATE_DIR` | Local override only. Host path mounted on `/app/data` when state is not `./data`. SGP1 mounts `/data/state/data` read-only and does not use this variable. |
| `SSH_PORT` | Port the ufw script keeps allowed. Default 22. |

`API_TOKEN` is the desk halt token. The status page does not accept it.

## Token

On the paper host:

```bash
openssl rand -hex 32
```

Put the output in the server env file as `STATUS_PAGE_TOKEN`. On SGP1 that
file is `/data/env/.env`. Do not echo it into a world-readable file, the
shell history you keep, or this repo. `chmod 600` the env file. Restart
only the status service after the change (the SGP1 `--no-deps
--force-recreate status` command in Rollback).

The compare is constant-time (`hmac.compare_digest` on SHA-256 digests).
The process logs that the token is unset when it is blank. It does not log
the value, and the page never returns it.

Clients send either header:

```bash
Authorization: Bearer "$SGP1_STATUS_TOKEN"
```

or Basic auth, where the password is the token and the username is ignored
(`curl -u "status:$SGP1_STATUS_TOKEN"`). A `?token=` query is ignored.

## Deploy without a paper restart

### SGP1 paper host

The api and paper containers belong to the compose project at
`/opt/mo-paper` (project name `mo-paper`, containers `mo-paper-api-1` and
`mo-paper-paper-1`). Do not deploy the status page as an override of that
project. A second `-f /opt/mo-paper/docker-compose.yml`, or `-p mo-paper`,
makes compose reconcile `mo-paper` and can recreate `api` and `paper`.

Use `deploy/status/docker-compose.sgp1.yml` on its own. On the host that
file is `/data/app/deploy/status/docker-compose.sgp1.yml`. Its project name
is `sgp1-status`. The command below passes `-p sgp1-status` as well, so the
project does not follow the directory you run it from.

| Path | Role |
|---|---|
| `/opt/mo-paper` | Existing api/paper compose project. Not passed to this command. |
| `/data/app` | Build context, and the bind mount on `/app`. |
| `/data/state/data` | State directory, mounted on `/app/data` read-only. |
| `/data/env/.env` | Env file for the status container, and compose interpolation (`--env-file`). |

`STATUS_TLS_SAN` in that file is
`DNS:localhost,IP:127.0.0.1,IP:178.128.215.94`, so the self-signed
certificate matches the paper host address.

Record the paper container start times first:

```bash
docker inspect -f '{{.Name}} {{.State.StartedAt}}' mo-paper-api-1 mo-paper-paper-1
```

Build and start only the status project:

```bash
docker compose \
  --env-file /data/env/.env \
  -p sgp1-status \
  -f /data/app/deploy/status/docker-compose.sgp1.yml \
  up -d --build
```

Confirm the paper containers were not recreated (same `StartedAt` as above)
and that the new containers belong to `sgp1-status`:

```bash
docker inspect -f '{{.Name}} {{.State.StartedAt}}' mo-paper-api-1 mo-paper-paper-1
docker compose \
  --env-file /data/env/.env \
  -p sgp1-status \
  -f /data/app/deploy/status/docker-compose.sgp1.yml \
  ps
```

The status service reads `/data/env/.env` (including `STATUS_PAGE_TOKEN`).
Caddy does not get that file. Caddy publishes host port 443. The status
process listens on 8088 inside the `sgp1-status` network only. The state
mount is read-only, so this process cannot write the book, the journal, or
the scan log. SQLite is opened with `mode=ro`. When that cannot create the
WAL `-shm` file on the read-only mount, the open falls back to SQLite's
immutable read-only mode so the book is still visible.

Fingerprint and proxy logs:

```bash
docker compose \
  --env-file /data/env/.env \
  -p sgp1-status \
  -f /data/app/deploy/status/docker-compose.sgp1.yml \
  logs caddy
```

### Local override

`docker-compose.status.yml` is an add-only override for a checkout that
already runs `docker-compose.yml` in the same directory. It is not the SGP1
layout. Do not use it in `/opt/mo-paper`.

From that local checkout (so `data/` is the state directory, including
`firm.db`, `paper_cash.json`, and `scan_summaries.jsonl`):

```bash
docker compose -f docker-compose.yml -f docker-compose.status.yml \
  up -d --no-deps --build status caddy
```

`--no-deps` plus the service names mean compose does not create or recreate
`paper` or `api`. Confirm the paper container's start time did not change:

```bash
docker compose -f docker-compose.yml ps paper
```

Caddy publishes host port 443. The status process listens on 8088 inside
the compose network only.

If `STATUS_PAGE_DOMAIN` is a DNS name that points at this host, Caddy
requests a Let's Encrypt certificate over TLS-ALPN on 443. Port 80 is not
required and the ufw script does not open it.

If the domain is blank, the Caddy entrypoint writes a self-signed
certificate and prints:

```text
SHA256 Fingerprint=AA:BB:...
sha256//<base64>
Client env: SGP1_STATUS_CERT_SHA256=AA:BB:...
Client env: SGP1_STATUS_PINNED_PUBKEY=sha256//<base64>
```

Read it from the log. The private key stays in the `status_certs` volume.
On SGP1, use the `logs caddy` command in the SGP1 section above. For the
local override:

```bash
docker compose -f docker-compose.yml -f docker-compose.status.yml logs caddy
```

To print the same values for a certificate you already have:

```bash
sh scripts/status_cert_fingerprint.sh /path/to/status.crt
```

Host-only (no compose), bound to localhost, with Caddy or another proxy in
front: `python scripts/run_status_page.py`. That still does not start paper.

## Firewall

`scripts/ufw_status_443.sh` adds an ALLOW for SSH and an ALLOW for 443/tcp
when those rules are missing. It does not enable ufw, does not change the
default policy, and does not delete a rule. Adding an allow cannot close
access that is already open.

```bash
sudo SSH_PORT=22 sh scripts/ufw_status_443.sh --dry-run
sudo SSH_PORT=22 sh scripts/ufw_status_443.sh
sudo ufw status verbose
```

If ufw is inactive, the script stores the rules and stops. Current access
is unchanged. Turning the firewall on is a separate decision, after you
have read `ufw status verbose` and confirmed the SSH allow is present.
This runbook does not do that step, because enabling a default-deny policy
would drop every other port.

## Client box

Store the secret in an env file the client process already treats as
secret, mode 600, outside this repo:

```bash
install -m 600 /dev/null /etc/sgp1-status.env
```

```bash
SGP1_STATUS_URL=https://status.example
SGP1_STATUS_TOKEN=<paste from the operator>
# Self-signed only. Omit both when Let's Encrypt is in front.
SGP1_STATUS_CERT_SHA256=AA:BB:CC:...
SGP1_STATUS_PINNED_PUBKEY=sha256//<base64>
```

`SGP1_STATUS_TOKEN` is the same string as the server's `STATUS_PAGE_TOKEN`.

Let's Encrypt (hostname matches the certificate):

```bash
set -a
. /etc/sgp1-status.env
set +a

curl --fail --silent --show-error \
  --header "Authorization: Bearer ${SGP1_STATUS_TOKEN}" \
  "${SGP1_STATUS_URL}/api/status"
```

Self-signed, pin the public key. `--pinnedpubkey` rejects a different key.
`--insecure` skips the public-CA check, which a self-signed cert cannot
pass; the pin is what authenticates the server. Do not use `--insecure`
without the pin.

```bash
curl --fail --silent --show-error \
  --insecure \
  --pinnedpubkey "${SGP1_STATUS_PINNED_PUBKEY}" \
  --header "Authorization: Bearer ${SGP1_STATUS_TOKEN}" \
  "${SGP1_STATUS_URL}/api/status"
```

Or check the certificate fingerprint before trusting the body. Abort when
it differs from `SGP1_STATUS_CERT_SHA256`:

```bash
host=$(printf '%s' "$SGP1_STATUS_URL" | sed -E 's#^https://([^/:]+).*#\1#')
actual=$(echo | openssl s_client -connect "${host}:443" -servername "$host" 2>/dev/null \
  | openssl x509 -noout -fingerprint -sha256 \
  | sed -E 's/^[Ss][Hh][Aa]256 [Ff]ingerprint=//')
want=$(printf '%s' "$SGP1_STATUS_CERT_SHA256" | tr '[:lower:]' '[:upper:]')
actual=$(printf '%s' "$actual" | tr '[:lower:]' '[:upper:]')
test "$actual" = "$want"

curl --fail --silent --show-error \
  --insecure \
  --pinnedpubkey "${SGP1_STATUS_PINNED_PUBKEY}" \
  --header "Authorization: Bearer ${SGP1_STATUS_TOKEN}" \
  "${SGP1_STATUS_URL}/api/status"
```

Basic auth works the same way, with the token as the password:

```bash
curl --fail --silent --show-error \
  --insecure \
  --pinnedpubkey "${SGP1_STATUS_PINNED_PUBKEY}" \
  --user "status:${SGP1_STATUS_TOKEN}" \
  "${SGP1_STATUS_URL}/api/status"
```

The HTML page is `GET /` with the same header. A browser will prompt for
Basic auth.

Per-IP limit defaults to 30 requests in 60 seconds. A 429 carries
`Retry-After`. Poll slower than that.

## Rollback

Stop the two status containers. The paper worker is not one of them.

On SGP1, stay on project `sgp1-status`. This does not address `/opt/mo-paper`:

```bash
docker compose \
  --env-file /data/env/.env \
  -p sgp1-status \
  -f /data/app/deploy/status/docker-compose.sgp1.yml \
  stop
docker compose \
  --env-file /data/env/.env \
  -p sgp1-status \
  -f /data/app/deploy/status/docker-compose.sgp1.yml \
  rm -f
```

Local override:

```bash
docker compose -f docker-compose.yml -f docker-compose.status.yml stop caddy status
docker compose -f docker-compose.yml -f docker-compose.status.yml rm -f caddy status
```

To drop the 443 allow after you have looked at the numbered rules, delete
that one rule by the number `ufw status numbered` prints. Do not reset the
firewall and do not remove the SSH rule.

```bash
sudo ufw status numbered
# sudo ufw delete <number of the 443 allow only>
```

Clear `STATUS_PAGE_TOKEN` in the server env file to disable the page
without removing the containers. The process keeps serving 503 until the
token is set again. Restart the status service only.

SGP1 (`/data/env/.env`, then this command):

```bash
docker compose \
  --env-file /data/env/.env \
  -p sgp1-status \
  -f /data/app/deploy/status/docker-compose.sgp1.yml \
  up -d --no-deps --force-recreate status
```

Local override:

```bash
docker compose -f docker-compose.yml -f docker-compose.status.yml \
  up -d --no-deps --force-recreate status
```

## SHA files

HEAD and `DEPLOYED_SHA` are shown separately. HEAD is the `GIT_SHA`
environment variable, then `/app/GIT_SHA` (or `<checkout>/GIT_SHA`), then
`git rev-parse HEAD` when `.git` exists. `DEPLOYED_SHA` is
`/app/data/DEPLOYED_SHA` or `<checkout>/data/DEPLOYED_SHA`. See
`docs/runbooks/desk_deployed_sha.md` for how those files are written. The
status page only reads them.
