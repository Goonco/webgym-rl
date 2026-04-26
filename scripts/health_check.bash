#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/setting.sh"

echo "[1/3] checking fixture website"
curl -fsS "http://127.0.0.1:${PORT_FIXTURE_WEBSITE}/counter.html" > /dev/null

echo "[2/3] checking omnibox"
curl -fsS -H "x-api-key: default_key" "http://127.0.0.1:${PORT_OMNIBOX_MASTER}/info" > /dev/null

echo "[3/3] checking gateway"
curl -fsS "http://127.0.0.1:${PORT_GATEWAY}/health" > /dev/null

echo "ok"
