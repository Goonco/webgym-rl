#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/setting.sh"

echo "[1/3] checking gateway"
curl -fsS "http://${GATEWAY_HOST}:${GATEWAY_PORT}/health" > /dev/null

echo "[2/2] checking omnibox"
curl -fsS -H "x-api-key: default_key" "http://${OMNIBOX_HOST}:${OMNIBOX_MASTER_PORT}/info" > /dev/null

echo "ok"
