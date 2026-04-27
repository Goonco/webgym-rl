#!/usr/bin/env bash

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
readonly TEST_DIR="$ROOT_DIR/tests"
readonly FIXTURE_DIR="$TEST_DIR/fixtures"

readonly LOG_DIR="${LOG_DIR:-$ROOT_DIR/logs}"
readonly LOG_FILE="${LOG_FILE:-$LOG_DIR/e2e_$(date +%Y%m%d_%H%M%S).log}"

# External Ports
readonly PORT_FIXTURE_WEBSITE=8123
readonly PORT_OMNIBOX_MASTER=5500
readonly PORT_GATEWAY=18000

# Internal Ports
readonly PORT_OMNIBOX_REDIS=6379
readonly PORT_OMNIBOX_NODE=8080
readonly PORT_OMNIBOX_INSTANCE_START=9000

# Settings
readonly OMNIBOX_INSTANCE=4
readonly OMNIBOX_MASTER_WORKERS=4
readonly OMNIBOX_NODE_WORKERS=2
readonly WEBGYM_RL_CONFIG="$ROOT_DIR/config.json"
readonly WITH_FIXTURE_WEBSITE=false
