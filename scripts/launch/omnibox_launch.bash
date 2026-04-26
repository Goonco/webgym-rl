#!/usr/bin/env bash
set -euo pipefail
source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/../setting.sh"

readonly DEPLOY_DIR="$ROOT_DIR/environment/webgym/omniboxes/deploy"
readonly REDIS_DATA_DIR="$DEPLOY_DIR/redis-data"

mkdir -p "$REDIS_DATA_DIR"

cd "$DEPLOY_DIR"
printf 'Executing "python deploy.py %s %s %s --master-port %s --node-port %s --instance-start-port %s --redis-port %s"\n\n' \
  "$OMNIBOX_INSTANCE" \
  "$OMNIBOX_MASTER_WORKERS" \
  "$OMNIBOX_NODE_WORKERS" \
  "$PORT_OMNIBOX_MASTER" \
  "$PORT_OMNIBOX_NODE" \
  "$PORT_OMNIBOX_INSTANCE_START" \
  "$PORT_OMNIBOX_REDIS"
exec python deploy.py \
  "$OMNIBOX_INSTANCE" \
  "$OMNIBOX_MASTER_WORKERS" \
  "$OMNIBOX_NODE_WORKERS" \
  --master-port "$PORT_OMNIBOX_MASTER" \
  --node-port "$PORT_OMNIBOX_NODE" \
  --instance-start-port "$PORT_OMNIBOX_INSTANCE_START" \
  --redis-port "$PORT_OMNIBOX_REDIS"