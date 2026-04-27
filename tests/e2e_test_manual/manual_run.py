import time
from pathlib import Path
from typing import Any

from .manual_runner import ManualRunner

here_dir = Path(__file__).resolve().parent
base_dir = (here_dir / "../../").resolve()

# ============================================================
# User-defined settings
# Modify only the values below for testing.
# ============================================================

TASK_ID = "form"
SESSION_ID = int(time.time() * 1000)
CONFIG_PATH = (base_dir / "./tests/fixtures/config/test.json").resolve()
ACTIONS: list[list[dict[str, Any]]] = [
    [
        {
            "action_type": "CLICK",
            "button": "left",
            "num_clicks": 1,
            "x": 849,
            "y": 303,
        },
        {
            "action_type": "HOTKEY",
            "keys": ["ControlOrMeta", "a"],
        },
        {
            "action_type": "TYPING",
            "text": "1975",
        },
    ]
]
MAX_TRAJECTORY_IMAGES = 4
MAX_AGENT_STEPS = 50

# ============================================================


def main() -> None:
    runner = ManualRunner(
        task_id=TASK_ID, session_id=SESSION_ID, actions=ACTIONS, config_path=CONFIG_PATH
    )
    runner.run()


if __name__ == "__main__":
    main()
