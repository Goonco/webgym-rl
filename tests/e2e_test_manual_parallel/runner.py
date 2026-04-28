import json
import random
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Optional

from tests.util import assert_ok_response, decode_png_base64, post


class Runner:
    def __init__(
        self,
        *,
        task_id: str,
        session_id: int,
        actions: Iterable[list[dict[str, Any]]],
        config_path: Path,
        timestamp: str,
    ):
        self.task_id = task_id
        self.session_id = session_id
        self.actions = actions
        self.rng = random.Random(session_id)

        self.start_delay_range = (0.0, 1.5)
        self.action_delay_range = (0.2, 1.0)
        self.reward_delay_range = (0.0, 0.1)

        here_dir = Path(__file__).resolve().parent
        base_dir = (here_dir / "../../").resolve()
        self.snapshot_dir = (
            base_dir
            / f"./tests/e2e_test_manual_parallel/__snapshots__/{timestamp}_{task_id}/sid_{session_id}"
        )

        with open(config_path, "r", encoding="utf-8") as f:
            config: dict[str, Any] = json.load(f)

        gateway = config["gateway"]
        self.url = f"http://{gateway['host']}:{gateway['port']}"

    def _sleep_jitter(self, delay_range: tuple[float, float]) -> None:
        low, high = delay_range
        if high <= 0:
            return
        time.sleep(self.rng.uniform(low, high))

    def run(
        self,
    ):
        step = self._step_gen()

        self._sleep_jitter(self.start_delay_range)
        start_response = post(
            self.url,
            {
                "op": "start",
                "session_id": self.session_id,
                "task_id": self.task_id,
            },
        )
        self._check_and_save_response("start", next(step), start_response)

        for action_batch in self.actions:
            self._sleep_jitter(self.action_delay_range)
            action_response = post(
                self.url,
                {
                    "op": "action",
                    "session_id": self.session_id,
                    "task_id": self.task_id,
                    "include_a11y": True,
                    "actions": action_batch,
                },
            )
            self._check_and_save_response("action", next(step), action_response)

        self._sleep_jitter(self.reward_delay_range)
        reward_response = post(
            self.url,
            {
                "op": "reward",
                "session_id": self.session_id,
                "task_id": self.task_id,
            },
        )
        self._check_and_save_response("reward", next(step), reward_response)

    def _step_gen(self):
        step = 0
        while True:
            yield step
            step += 1

    def _create_snapshots(
        self,
        op: str,
        step: int,
        *,
        screenshot: Optional[bytes] = None,
        a11y_tree: Optional[str] = None,
        reward: Optional[float] = None,
    ):
        step_snapshot_dir = self.snapshot_dir / f"./{step}_{op}"
        step_snapshot_dir.mkdir(parents=True)

        if screenshot is not None:
            snapshot_path = step_snapshot_dir / "screenshot.png"
            snapshot_path.write_bytes(screenshot)

        if a11y_tree is not None:
            allytree_path = step_snapshot_dir / "a11y_tree.txt"
            allytree_path.write_text(a11y_tree)

        if reward is not None:
            reward_path = step_snapshot_dir / "reward.txt"
            reward_path.write_text(str(reward))

    def _check_and_save_response(self, op: str, step: int, response: dict):
        assert_ok_response(response, self.session_id, self.task_id)

        if op == "reward":
            self._create_snapshots(op, step, reward=response["reward"])

        else:
            image = response["image"]
            screenshot = decode_png_base64(image["data"])
            a11y_tree = response["text"]
            self._create_snapshots(op, step, screenshot=screenshot, a11y_tree=a11y_tree)
