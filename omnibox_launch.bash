#!/usr/bin/env bash
set -euo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/setting.sh"

readonly DEPLOY_DIR="$ROOT_DIR/environment/webgym/omniboxes/deploy"
readonly REDIS_DATA_DIR="$DEPLOY_DIR/redis-data"

mkdir -p "$REDIS_DATA_DIR"

cd "$DEPLOY_DIR"
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