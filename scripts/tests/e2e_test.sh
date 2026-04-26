#!/usr/bin/env bash
set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/test_setup.sh"

echo "Start Testing"

logstep "[1/2] checking handle start"
python "$TEST_DIR/test_handle_start.py"

logstep "[2/2] checking handle action and reward"
python "$TEST_DIR/test_handle_action_and_reward.py"