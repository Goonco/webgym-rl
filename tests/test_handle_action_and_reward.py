#!/usr/bin/env python

import base64
import difflib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

GATEWAY_URL = "http://127.0.0.1:18000/v1/env"
SESSION_ID = int(time.time() * 1000)
TASK_ID = "counter-test"

SNAPSHOT_DIR = Path("tests/snapshots/test_handle_action_and_reward")
SCREENSHOT_NAME = "screenshot.png"
A11Y_TREE_NAME = "a11y_tree.txt"
REWARD_NAME = "reward.json"

PLUS_BUTTON_X = 696
PLUS_BUTTON_Y = 480


def post(payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        GATEWAY_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(exc.read().decode("utf-8"), file=sys.stderr)
        raise


def decode_png_base64(data: str) -> bytes:
    raw = base64.b64decode(data, validate=True)
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise AssertionError("image.data is not a PNG payload")
    if len(raw) < 1024:
        raise AssertionError(f"image.data is unexpectedly small: {len(raw)} bytes")
    return raw


def assert_ok_response(response: dict, op_name: str) -> None:
    if response.get("status") != "ok":
        raise AssertionError(f"{op_name}: unexpected status: {response}")
    if response.get("session_id") != SESSION_ID:
        raise AssertionError(f"{op_name}: unexpected session_id: {response}")
    if response.get("task_id") != TASK_ID:
        raise AssertionError(f"{op_name}: unexpected task_id: {response}")


def compare_or_create_snapshots(screenshot: bytes, a11y_tree: str, reward: dict) -> None:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    reward_json = json.dumps(reward, indent=2, sort_keys=True) + "\n"

    mismatches = []
    for file_name, mode, current in (
        (SCREENSHOT_NAME, "bytes", screenshot),
        (A11Y_TREE_NAME, "text", a11y_tree),
        (REWARD_NAME, "text", reward_json),
    ):
        snapshot_path = SNAPSHOT_DIR / file_name

        if not snapshot_path.exists():
            write_snapshot(snapshot_path, mode, current)
            print(f"created snapshot: {snapshot_path}")
            continue

        if mode == "bytes":
            if current != snapshot_path.read_bytes():
                mismatches.append((file_name, mode, current, snapshot_path))
        elif current != snapshot_path.read_text(encoding="utf-8"):
            mismatches.append((file_name, mode, current, snapshot_path))

    if not mismatches:
        print("handle_action snapshot test pass")
        return

    for file_name, mode, current, snapshot_path in mismatches:
        print(f"\nsnapshot mismatch: {file_name}")
        print(f"snapshot: {snapshot_path}")
        if mode == "text":
            print_text_diff(snapshot_path, current)
        else:
            print_binary_diff(snapshot_path, current)

    if ask_to_update_snapshots():
        for _, mode, current, snapshot_path in mismatches:
            write_snapshot(snapshot_path, mode, current)
            print(f"updated snapshot: {snapshot_path}")
        return

    raise AssertionError("snapshot mismatch")


def write_snapshot(snapshot_path: Path, mode: str, current: bytes | str) -> None:
    if mode == "bytes":
        assert isinstance(current, bytes)
        snapshot_path.write_bytes(current)
    else:
        assert isinstance(current, str)
        snapshot_path.write_text(current, encoding="utf-8")


def print_text_diff(snapshot_path: Path, current: str) -> None:
    expected = snapshot_path.read_text(encoding="utf-8").splitlines()
    actual = current.splitlines()

    diff = difflib.unified_diff(
        expected,
        actual,
        fromfile=str(snapshot_path),
        tofile="current",
        lineterm="",
    )
    print("\n".join(diff))


def print_binary_diff(snapshot_path: Path, current: bytes) -> None:
    expected = snapshot_path.read_bytes()
    actual = current

    first_diff_at = next(
        (
            index
            for index, (expected_byte, actual_byte) in enumerate(zip(expected, actual))
            if expected_byte != actual_byte
        ),
        min(len(expected), len(actual)),
    )

    expected_byte = expected[first_diff_at] if first_diff_at < len(expected) else None
    actual_byte = actual[first_diff_at] if first_diff_at < len(actual) else None
    print(
        "binary diff: "
        f"snapshot_size={len(expected)} bytes, "
        f"result_size={len(actual)} bytes, "
        f"first_diff_at={first_diff_at}, "
        f"snapshot_byte={expected_byte}, "
        f"result_byte={actual_byte}"
    )


def ask_to_update_snapshots() -> bool:
    try:
        answer = input("\nUpdate snapshot(s) with current result? [y/N] ")
    except EOFError:
        return False
    return answer.strip().lower() == "y"


def main() -> None:
    terminal_requested = False

    post(
        {
            "op": "start",
            "session_id": SESSION_ID,
            "task_id": TASK_ID,
        }
    )

    try:
        action_response = post(
            {
                "op": "action",
                "session_id": SESSION_ID,
                "task_id": TASK_ID,
                "include_a11y": True,
                "actions": [
                    {
                        "action_type": "CLICK",
                        "button": "left",
                        "x": PLUS_BUTTON_X,
                        "y": PLUS_BUTTON_Y,
                        "num_clicks": 5,
                    }
                ],
            }
        )
        assert_ok_response(action_response, "action")

        image = action_response.get("image")
        if not isinstance(image, dict):
            raise AssertionError(f"missing image payload: {action_response}")

        screenshot = decode_png_base64(image.get("data", ""))

        a11y_tree = action_response.get("text")
        if not isinstance(a11y_tree, str) or not a11y_tree.strip():
            raise AssertionError(f"missing a11y tree: {action_response}")

        terminal_requested = True
        done_response = post(
            {
                "op": "action",
                "session_id": SESSION_ID,
                "task_id": TASK_ID,
                "actions": [{"action_type": "DONE"}],
            }
        )
        assert_ok_response(done_response, "done")

        reward_response = post(
            {
                "op": "reward",
                "session_id": SESSION_ID,
                "task_id": TASK_ID,
            }
        )
        assert_ok_response(reward_response, "reward")

        if reward_response.get("reward") != 1.0:
            raise AssertionError(f"expected reward=1.0, got: {reward_response}")

        compare_or_create_snapshots(screenshot, a11y_tree, reward_response)
        print(f"snapshot dir: {SNAPSHOT_DIR}")

    finally:
        if not terminal_requested:
            try:
                post(
                    {
                        "op": "action",
                        "session_id": SESSION_ID,
                        "task_id": TASK_ID,
                        "actions": [{"action_type": "FAIL"}],
                    }
                )
            except Exception as exc:
                print(f"cleanup failed: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
