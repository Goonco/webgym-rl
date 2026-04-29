#!/usr/bin/env bash

readonly ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly TEST_DIR="$ROOT_DIR/tests"
readonly FIXTURE_DIR="$TEST_DIR/fixtures"

# =============================================================================================
# User-defined settings
# Modify only the values below for testing.
# 
# * Use the appropriate WEBGYM_RL_CONFIG for the target test
# * Make sure to set WITH_FIXTURE_WEBSITE=true when using fixture websites
# =============================================================================================

readonly WEBGYM_RL_CONFIG="$FIXTURE_DIR/config/config-single.json"

readonly WITH_FIXTURE_WEBSITE=true
readonly FIXTURE_WEBSITE_PORT=8123

# =============================================================================================

json_get(){
    jq -r "$1" "$WEBGYM_RL_CONFIG"
}

readonly GATEWAY_HOST="$(jq -r '.gateway.host' "$WEBGYM_RL_CONFIG")"
readonly GATEWAY_PORT="$(jq -r '.gateway.port' "$WEBGYM_RL_CONFIG")"

readonly OMNIBOX_HOST="$(jq -r '.omnibox.host' "$WEBGYM_RL_CONFIG")"
readonly OMNIBOX_MASTER_PORT="$(jq -r '.omnibox.master_port' "$WEBGYM_RL_CONFIG")"
readonly OMNIBOX_NODE_PORT="$(jq -r '.omnibox.node_port' "$WEBGYM_RL_CONFIG")"
readonly OMNIBOX_INSTANCE_START_PORT="$(jq -r '.omnibox.instance_start_port' "$WEBGYM_RL_CONFIG")"
readonly OMNIBOX_REDIS_PORT="$(jq -r '.omnibox.redis_port' "$WEBGYM_RL_CONFIG")"

readonly OMNIBOX_INSTANCE="$(jq -r '.omnibox.instances' "$WEBGYM_RL_CONFIG")"
readonly OMNIBOX_MASTER_WORKERS="$(jq -r '.omnibox.master_workers' "$WEBGYM_RL_CONFIG")"
readonly OMNIBOX_NODE_WORKERS="$(jq -r '.omnibox.node_workers' "$WEBGYM_RL_CONFIG")"

readonly OMNIBOX_API_KEY="$(jq -r '.omnibox.api_key' "$WEBGYM_RL_CONFIG")"