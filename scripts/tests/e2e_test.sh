#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../setting.sh"
PIDS=()

mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1
echo "Logging to $LOG_FILE"

cleanup() {
  local pid
  for pid in "${PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
  done
}

wait_for_http() {
  local name="$1"
  local command="$2"
  local attempts="${3:-60}"
  local sleep_seconds="${4:-1}"
  local i

  for ((i = 1; i <= attempts; i++)); do
    if eval "$command" >/dev/null 2>&1; then
      echo "$name is ready"
      return 0
    fi
    sleep "$sleep_seconds"
  done

  echo "timed out waiting for $name" >&2
  return 1
}

logstep() {
  local msg="$1"
  printf '\n'
  printf '============================================================\n'
  printf '  >>> %s\n' "$msg"
  printf '============================================================\n'
}

trap cleanup EXIT INT TERM

logstep "#1 launching webgym-rl server"
bash "$SCRIPT_DIR/launch/webgym_rl_launch.bash" &
PIDS+=("$!")
wait_for_http \
  "gateway" \
  "curl -fsS http://127.0.0.1:${PORT_GATEWAY}/health"

logstep "#2 launching omnibox"
bash "$SCRIPT_DIR/launch/omnibox_launch.bash" &
PIDS+=("$!")
wait_for_http \
  "omnibox" \
  "curl -fsS -H \"x-api-key: default_key\" http://127.0.0.1:${PORT_OMNIBOX_MASTER}/info"


if [[ "$WITH_FIXTURE_WEBSITE" == "true" ]]; then
  logstep "#3 launching fixture website"
  bash "$SCRIPT_DIR/launch/fixture_web_launch.bash" &
  PIDS+=("$!")

  wait_for_http \
    "fixture website" \
    "curl -fsS http://127.0.0.1:${PORT_FIXTURE_WEBSITE}/counter.html"
else
  logstep "#3 skipping fixture website"
fi

logstep "#4 running health check"
bash "$SCRIPT_DIR/health_check.bash"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  source "$ROOT_DIR/.env"
  set +a
fi

logstep "#5 e2e_test"
(
  cd "$ROOT_DIR"
  python -m tests.e2e_test.run
)