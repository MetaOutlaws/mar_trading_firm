#!/bin/sh
# Terminate TLS on 443 for the status page.
#
# Let's Encrypt when STATUS_PAGE_DOMAIN is a DNS name. Otherwise mint a
# self-signed certificate (or reuse one already in /certs) and print its
# SHA-256 fingerprint plus the curl --pinnedpubkey pin.
#
# This script does not read the status bearer token and does not start
# the paper worker.

set -eu

DOMAIN="${STATUS_PAGE_DOMAIN:-}"
EMAIL="${STATUS_TLS_EMAIL:-}"
SAN="${STATUS_TLS_SAN:-DNS:localhost,IP:127.0.0.1}"
CERT_DIR=/certs
RUNTIME=/etc/caddy/Caddyfile.runtime
UPSTREAM="${STATUS_UPSTREAM:-status:8088}"

mkdir -p "$CERT_DIR"

is_dns() {
  printf '%s' "$1" | grep -Eq '^[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$'
}

is_email() {
  printf '%s' "$1" | grep -Eq '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
}

safe_san() {
  printf '%s' "$1" | grep -Eq '^(DNS:[A-Za-z0-9.-]+|IP:[0-9a-fA-F:.]+)(,(DNS:[A-Za-z0-9.-]+|IP:[0-9a-fA-F:.]+))*$'
}

write_proxy() {
  cat <<EOF
	encode gzip
	header {
		Strict-Transport-Security "max-age=31536000"
		X-Content-Type-Options nosniff
		Referrer-Policy no-referrer
		-Server
	}
	reverse_proxy ${UPSTREAM} {
		header_up X-Real-IP {remote_host}
	}
EOF
}

if is_dns "$DOMAIN"; then
  {
    echo "{"
    if is_email "$EMAIL"; then
      echo "	email ${EMAIL}"
    fi
    echo "}"
    echo "${DOMAIN} {"
    write_proxy
    echo "}"
  } > "$RUNTIME"
  echo "status-tls: Let's Encrypt for ${DOMAIN} on 443"
else
  if [ -n "$DOMAIN" ]; then
    echo "status-tls: STATUS_PAGE_DOMAIN is not a DNS name; using a self-signed certificate" >&2
  fi
  if ! command -v openssl >/dev/null 2>&1; then
    if command -v apk >/dev/null 2>&1; then
      apk add --no-cache openssl
    else
      echo "status-tls: openssl is required to mint a self-signed certificate" >&2
      exit 1
    fi
  fi
  if ! safe_san "$SAN"; then
    SAN="DNS:localhost,IP:127.0.0.1"
  fi
  if [ ! -f "$CERT_DIR/status.crt" ] || [ ! -f "$CERT_DIR/status.key" ]; then
    openssl req -x509 -newkey rsa:2048 -sha256 -days 825 -nodes \
      -keyout "$CERT_DIR/status.key" \
      -out "$CERT_DIR/status.crt" \
      -subj "/CN=sgp1-status" \
      -addext "subjectAltName=${SAN}"
    chmod 600 "$CERT_DIR/status.key"
  fi
  fp=$(openssl x509 -in "$CERT_DIR/status.crt" -noout -fingerprint -sha256 \
    | sed -E 's/^[Ss][Hh][Aa]256 [Ff]ingerprint=//')
  spki=$(openssl x509 -in "$CERT_DIR/status.crt" -pubkey -noout \
    | openssl pkey -pubin -outform DER \
    | openssl dgst -sha256 -binary \
    | openssl base64 -A)
  {
    echo "SHA256 Fingerprint=${fp}"
    echo "sha256//${spki}"
  } | tee "$CERT_DIR/FINGERPRINT.txt"
  echo "Client env: SGP1_STATUS_CERT_SHA256=${fp}"
  echo "Client env: SGP1_STATUS_PINNED_PUBKEY=sha256//${spki}"
  {
    echo ":443 {"
    echo "	tls ${CERT_DIR}/status.crt ${CERT_DIR}/status.key"
    write_proxy
    echo "}"
  } > "$RUNTIME"
  echo "status-tls: self-signed certificate on 443"
fi

exec caddy run --config "$RUNTIME" --adapter caddyfile
