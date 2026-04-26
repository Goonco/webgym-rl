set -euo pipefail

source "$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/test_setup.sh"

set -a
source .env
set +a

echo "Start Testing"

logstep "[1/1] gpt_e2e_test start"
python "$TEST_DIR/test_gpt.py"