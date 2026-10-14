#!/bin/sh
# Print the SHA-256 fingerprint and the curl --pinnedpubkey pin for a cert.
# Usage: status_cert_fingerprint.sh path/to/cert.pem
# Does not print the private key.

set -eu

cert=${1:?cert path required}
openssl x509 -in "$cert" -noout -fingerprint -sha256
spki=$(openssl x509 -in "$cert" -pubkey -noout \
  | openssl pkey -pubin -outform DER \
  | openssl dgst -sha256 -binary \
  | openssl base64 -A)
printf 'sha256//%s\n' "$spki"
