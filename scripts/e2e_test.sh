#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/setting.sh"
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

logstep "[1/4] launching webgym-rl server"
bash "$SCRIPT_DIR/start/webgym_rl_start.bash" &
PIDS+=("$!")
wait_for_http \
  "gateway" \
  "curl -fsS http://127.0.0.1:${PORT_GATEWAY}/health"

logstep "[2/4] launching omnibox"
bash "$SCRIPT_DIR/start/omnibox_start.bash" &
PIDS+=("$!")
wait_for_http \
  "omnibox" \
  "curl -fsS -H \"x-api-key: default_key\" http://127.0.0.1:${PORT_OMNIBOX_MASTER}/info"

logstep "[3/4] launching fixture website"
bash "$SCRIPT_DIR/start/fixture_start.bash" &
PIDS+=("$!")
wait_for_http \
  "fixture website" \
  "curl -fsS http://127.0.0.1:${PORT_FIXTURE_WEBSITE}/counter.html"

logstep "[4/4] running health check"
bash "$SCRIPT_DIR/health_check.bash"

echo "Start Testing"

logstep "[1/2] checking handle start"
python "$TEST_DIR/test_handle_start.py"

logstep "[2/2] checking handle action and reward"
python "$TEST_DIR/test_handle_action_and_reward.py"