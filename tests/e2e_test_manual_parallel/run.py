import argparse
import asyncio
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

from .runner import Runner

# ============================================================
# User-defined settings
# Modify only the values below for testing.
# ============================================================

TASK_ID = "counter"

ACTION: list[dict[str, Any]] = [
    {
        "action_type": "CLICK",
        "button": "left",
        "num_clicks": 1,
        "x": 696,
        "y": 475,
    },
]

CONCURRENCY = 512
MAX_STEPS = 5

# ============================================================


def repeat_action() -> Iterator[list[dict[str, Any]]]:
    for _ in range(MAX_STEPS):
        yield ACTION
    yield [
        {
            "action_type": "DONE",
        }
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config-path",
        type=Path,
        required=True,
        help="Path to the config JSON file",
    )
    return parser.parse_args()


def run_single_task(*, config_path: Path, session_id: int, timestamp: str) -> None:
    runner = Runner(
        task_id=TASK_ID,
        session_id=session_id,
        actions=repeat_action(),
        config_path=config_path,
        timestamp=timestamp,
    )

    runner.run()


async def run_single_task_async(*, config_path: Path, session_id: int, timestamp: str) -> None:
    await asyncio.to_thread(
        run_single_task, config_path=config_path, session_id=session_id, timestamp=timestamp
    )


async def main_async() -> None:
    args = parse_args()
    config_path = args.config_path.resolve()

    timestamp = datetime.now().strftime("%y%m%d-%H%M%S")

    jobs = [
        run_single_task_async(config_path=config_path, session_id=session_id, timestamp=timestamp)
        for session_id in range(CONCURRENCY)
    ]

    await asyncio.gather(*jobs)


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
