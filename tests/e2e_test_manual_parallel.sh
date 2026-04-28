#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/setting.sh"
PIDS=()

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
  local msg=">>> $1"
  local width=72
  local border
  local content_width=$((width - 4))

  border="$(printf '%*s' "$content_width" '' | tr ' ' '=')"

  printf '\n'
  printf '# %s #\n' "$border"
  printf '# %-*s #\n' "$content_width" "$msg"
  printf '# %s #\n' "$border"
  printf '\n'
}

trap cleanup EXIT INT TERM

logstep "#1 launching webgym-rl server"
(
  cd "$ROOT_DIR" || exit 1
  printf 'Executing "python -m src.server %s"\n\n' \
    "$WEBGYM_RL_CONFIG"
  exec python -m src.server "$WEBGYM_RL_CONFIG"
) &
PIDS+=("$!")
wait_for_http \
  "gateway" \
  "curl -fsS http://${GATEWAY_HOST}:${GATEWAY_PORT}/health"

logstep "#2 launching omnibox"
(
  readonly DEPLOY_DIR="$ROOT_DIR/environment/webgym/omniboxes/deploy"
  readonly REDIS_DATA_DIR="$DEPLOY_DIR/redis-data"

  mkdir -p "$REDIS_DATA_DIR"

  cd "$DEPLOY_DIR" || exit 1
  printf 'Executing "python deploy.py %s %s %s --master-port %s --node-port %s --instance-start-port %s --redis-port %s"\n\n' \
    "$OMNIBOX_INSTANCE" \
    "$OMNIBOX_MASTER_WORKERS" \
    "$OMNIBOX_NODE_WORKERS" \
    "$OMNIBOX_MASTER_PORT" \
    "$OMNIBOX_NODE_PORT" \
    "$OMNIBOX_INSTANCE_START_PORT" \
    "$OMNIBOX_REDIS_PORT"

  exec python deploy.py \
    "$OMNIBOX_INSTANCE" \
    "$OMNIBOX_MASTER_WORKERS" \
    "$OMNIBOX_NODE_WORKERS" \
    --master-port "$OMNIBOX_MASTER_PORT" \
    --node-port "$OMNIBOX_NODE_PORT" \
    --instance-start-port "$OMNIBOX_INSTANCE_START_PORT" \
    --redis-port "$OMNIBOX_REDIS_PORT"
) &
PIDS+=("$!")
wait_for_http \
  "omnibox" \
  "curl -fsS -H \"x-api-key: ${OMNIBOX_API_KEY}\" http://${OMNIBOX_HOST}:${OMNIBOX_MASTER_PORT}/info"


if [[ "$WITH_FIXTURE_WEBSITE" == "true" ]]; then
  logstep "#3 launching fixture website"
  (
    cd "$ROOT_DIR" || exit 1
    printf 'Executing "python -m http.server %s --directory %s"\n\n' \
      "$FIXTURE_WEBSITE_PORT" \
      "$FIXTURE_DIR/website"
    exec python -m http.server "$FIXTURE_WEBSITE_PORT" --directory "$FIXTURE_DIR/website"
  ) &
  PIDS+=("$!")

  wait_for_http \
    "fixture website" \
    "curl -fsS http://127.0.0.1:${FIXTURE_WEBSITE_PORT}/index.html"
else
  logstep "#3 skipping fixture website"
fi


logstep "#4 e2e_test_manual"
(
  cd "$ROOT_DIR"
  python -m tests.e2e_test_manual_parallel.run --config-path "$WEBGYM_RL_CONFIG"
)