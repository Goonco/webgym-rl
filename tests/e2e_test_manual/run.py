import argparse
import time
from pathlib import Path
from typing import Any

from .runner import Runner

# ============================================================
# User-defined settings
# Modify only the values below for testing.
# ============================================================

TASK_ID = "counter"
SESSION_ID = int(time.time() * 1000)
ACTIONS: list[list[dict[str, Any]]] = [
    [
        {
            "action_type": "CLICK",
            "x": 696,
            "y": 475,
        },
    ],
    [
        {"action_type": "CLICK", "num_clicks": 4},
    ],
]

# ============================================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config-path",
        type=Path,
        help="Path to the config JSON file",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = args.config_path.resolve()

    runner = Runner(
        task_id=TASK_ID,
        session_id=SESSION_ID,
        actions=ACTIONS,
        config_path=config_path,
    )
    runner.run()


if __name__ == "__main__":
    main()
