#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../setting.sh"

cd "$ROOT_DIR"
printf 'Executing "python -m http.server %s --directory %s"\n\n' \
  "$PORT_FIXTURE_WEBSITE" \
  "$FIXTURE_DIR/website"
exec python -m http.server "$PORT_FIXTURE_WEBSITE" --directory "$FIXTURE_DIR/website"
