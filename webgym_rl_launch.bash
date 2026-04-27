#!/usr/bin/env bash
set -euo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/setting.sh"

cd "$ROOT_DIR"

printf 'Executing "python -m src.server %s"\n\n' \
  "$WEBGYM_RL_CONFIG"

exec python -m src.server "$WEBGYM_RL_CONFIG"