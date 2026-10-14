#!/usr/bin/env bash
# Open TCP 443 for the SGP1 status page and keep operator SSH reachable.
#
# Adds allow rules only. Existing allow rules stay. The firewall is not
# enabled here, and the default policy is not changed, so this cannot close
# access that is open today. Read docs/runbooks/status_page.md before you
# enable ufw yourself.

set -euo pipefail

SSH_PORT="${SSH_PORT:-22}"
DRY_RUN=0

usage() {
  cat <<EOF
Usage: ufw_status_443.sh [--dry-run]

Ensures an ALLOW rule for SSH on port ${SSH_PORT} (override with SSH_PORT)
and an ALLOW rule for 443/tcp. Rules that are already present are left
alone. Run --dry-run to print the plan without calling ufw.
EOF
}

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    *)
      echo "Unknown argument: $arg" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ! [[ "$SSH_PORT" =~ ^[0-9]+$ ]] || [ "$SSH_PORT" -lt 1 ] || [ "$SSH_PORT" -gt 65535 ]; then
  echo "SSH_PORT must be a TCP port" >&2
  exit 2
fi

say() {
  printf '%s\n' "$*"
}

if [ "$DRY_RUN" -eq 1 ]; then
  say "dry-run: would read current ufw status and leave every existing allow in place"
  say "dry-run: would allow ${SSH_PORT}/tcp if that SSH rule is missing (operator ssh)"
  say "dry-run: would allow 443/tcp if that rule is missing (sgp1 status page)"
  say "dry-run: would not turn the firewall on and would not change the default policy"
  exit 0
fi

if ! command -v ufw >/dev/null 2>&1; then
  echo "ufw is not installed. No firewall change was made." >&2
  exit 1
fi

say "Current ufw status (read-only):"
ufw status verbose || true

status_text="$(ufw status)"

ssh_present=0
https_present=0
if printf '%s\n' "$status_text" | grep -Eq "^${SSH_PORT}/tcp[[:space:]]+ALLOW"; then
  ssh_present=1
fi
if printf '%s\n' "$status_text" | grep -Eq "^443/tcp[[:space:]]+ALLOW"; then
  https_present=1
fi

# SSH first. A later manual enable then still has an operator path.
if [ "$ssh_present" -eq 0 ]; then
  say "Adding allow for operator SSH on ${SSH_PORT}/tcp before the status rule."
  ufw allow "${SSH_PORT}/tcp" comment "operator ssh kept by status page script"
else
  say "SSH ${SSH_PORT}/tcp is already allowed. Leaving that rule as it is."
fi

if [ "$https_present" -eq 0 ]; then
  say "Adding allow for 443/tcp (sgp1 status page)."
  ufw allow 443/tcp comment "sgp1 status page"
else
  say "443/tcp is already allowed. Leaving that rule as it is."
fi

say "Done. Existing allow rules were not removed."
if printf '%s\n' "$status_text" | head -n 1 | grep -qi "inactive"; then
  say "ufw is inactive, so current access is unchanged."
  say "The allow rules above are stored for a later manual enable."
  say "This script stops here. Read 'ufw status verbose' before any enable."
fi
