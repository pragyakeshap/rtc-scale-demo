#!/usr/bin/env bash
set -euo pipefail

URL="${1:-http://localhost:8080/process?pixels=1280x720&iters=10}"
CONCURRENCY="${2:-20}"
REQUESTS="${3:-200}"

seq "${REQUESTS}" | xargs -n1 -P"${CONCURRENCY}" -I{} \
  curl -s -X POST "${URL}" >/dev/null

echo "Sent ${REQUESTS} requests at concurrency ${CONCURRENCY} to ${URL}"
