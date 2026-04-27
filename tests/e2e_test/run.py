import os
import time
from pathlib import Path

from .runner import Runner

here_dir = Path(__file__).resolve().parent
base_dir = (here_dir / "../../").resolve()

# ============================================================
# User-defined settings
# Modify only the values below for testing.
# ============================================================

TASK_ID = "form"
SESSION_ID = int(time.time() * 1000)
CONFIG_PATH = (base_dir / "./tests/fixtures/config/test.json").resolve()
MODEL = "gpt-5.4-mini"
API_KEY = os.environ.get("OPENAI_API_KEY")
MAX_STEPS = 10
MAX_TRAJECTORY_IMAGES = 4


# ============================================================


def main() -> None:
    if API_KEY is None:
        raise RuntimeError("OPENAI_API_KEY is required")
    runner = Runner(
        task_id=TASK_ID,
        session_id=SESSION_ID,
        config_path=CONFIG_PATH,
        model=MODEL,
        api_key=API_KEY,
        max_steps=MAX_STEPS,
        max_trajectory_images=MAX_TRAJECTORY_IMAGES,
    )
    runner.run()


if __name__ == "__main__":
    main()
