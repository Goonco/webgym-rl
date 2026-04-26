import base64
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, List, cast

from openai import OpenAI

ACTION_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "object",
        "properties": {
            "action_type": {"type": "string", "enum": ["MOVE_TO"]},
            "x": {"type": "integer"},
            "y": {"type": "integer"},
        },
        "required": ["action_type", "x", "y"],
        "additionalProperties": False,
    },
    {
        "type": "object",
        "properties": {
            "action_type": {"type": "string", "enum": ["CLICK"]},
            "button": {"type": "string", "enum": ["left"]},
            "x": {"type": "integer"},
            "y": {"type": "integer"},
            "num_clicks": {"type": "integer", "minimum": 1, "maximum": 10},
        },
        "required": ["action_type", "button", "x", "y", "num_clicks"],
        "additionalProperties": False,
    },
    {
        "type": "object",
        "properties": {
            "action_type": {"type": "string", "enum": ["DOUBLE_CLICK"]},
            "x": {"type": "integer"},
            "y": {"type": "integer"},
        },
        "required": ["action_type", "x", "y"],
        "additionalProperties": False,
    },
    {
        "type": "object",
        "properties": {
            "action_type": {"type": "string", "enum": ["SCROLL"]},
            "dx": {"type": "integer"},
            "dy": {"type": "integer"},
        },
        "required": ["action_type", "dx", "dy"],
        "additionalProperties": False,
    },
    {
        "type": "object",
        "properties": {
            "action_type": {"type": "string", "enum": ["TYPING"]},
            "text": {"type": "string"},
        },
        "required": ["action_type", "text"],
        "additionalProperties": False,
    },
    {
        "type": "object",
        "properties": {
            "action_type": {"type": "string", "enum": ["PRESS"]},
            "key": {"type": "string"},
        },
        "required": ["action_type", "key"],
        "additionalProperties": False,
    },
    {
        "type": "object",
        "properties": {
            "action_type": {"type": "string", "enum": ["HOTKEY"]},
            "keys": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["action_type", "keys"],
        "additionalProperties": False,
    },
    {
        "type": "object",
        "properties": {
            "action_type": {"type": "string", "enum": ["WAIT"]},
        },
        "required": ["action_type"],
        "additionalProperties": False,
    },
    {
        "type": "object",
        "properties": {
            "action_type": {"type": "string", "enum": ["DONE"]},
        },
        "required": ["action_type"],
        "additionalProperties": False,
    },
    {
        "type": "object",
        "properties": {
            "action_type": {"type": "string", "enum": ["FAIL"]},
        },
        "required": ["action_type"],
        "additionalProperties": False,
    },
]

ACTION_ALLOWED_FIELDS = {
    "MOVE_TO": {"action_type", "x", "y"},
    "CLICK": {"action_type", "button", "x", "y", "num_clicks"},
    "DOUBLE_CLICK": {"action_type", "x", "y"},
    "SCROLL": {"action_type", "dx", "dy"},
    "TYPING": {"action_type", "text"},
    "PRESS": {"action_type", "key"},
    "HOTKEY": {"action_type", "keys"},
    "WAIT": {"action_type"},
    "DONE": {"action_type"},
    "FAIL": {"action_type"},
}

TOOLS: List[Any] = [
    {
        "type": "function",
        "name": "webgym_start",
        "description": "Start the WebGym task. The harness always sends include_a11y=true.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "webgym_action",
        "description": (
            "Execute computer actions in WebGym. Choose actions from the current "
            "screenshot and accessibility tree. Do not assume coordinates that were "
            "not observed."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "actions": {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 5,
                    "items": {"anyOf": ACTION_SCHEMAS},
                }
            },
            "required": ["actions"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "webgym_reward",
        "description": "Request reward after the model has sent DONE or FAIL.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    },
]
MAX_TRAJECTORY_IMAGES = 4
MAX_AGENT_STEPS = 10

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_TASK_PATH = ROOT_DIR / "tests" / "fixtures" / "task" / "counter.json"
TASK_PATH = Path(os.environ.get("WEBGYM_TASK_PATH", str(DEFAULT_TASK_PATH)))

GATEWAY_URL = os.environ.get("WEBGYM_GATEWAY_URL", "http://127.0.0.1:18000") + "/v1/env"
SESSION_ID = int(time.time() * 1000)

MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or os.environ.get("openai_API_KEY")
SNAPSHOT_DIR = ROOT_DIR / "tests" / "snapshots" / "test_gpt"


def load_task(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(data, dict):
        return data

    if isinstance(data, list):
        task_id = os.environ.get("WEBGYM_TASK_ID")
        if task_id is None:
            if len(data) != 1:
                raise RuntimeError(
                    f"WEBGYM_TASK_ID is required when task fixture has {len(data)} tasks: {path}"
                )
            return data[0]

        for task in data:
            if str(task.get("task_id")) == task_id:
                return task

        raise RuntimeError(f"task_id={task_id!r} not found in {path}")

    raise RuntimeError(f"unsupported task fixture format: {path}")


TASK = load_task(TASK_PATH)
TASK_ID = str(TASK["task_id"])
TASK_NAME = str(TASK.get("task_name") or TASK.get("instruction") or TASK_ID)


def reset_snapshot_dir() -> None:
    if SNAPSHOT_DIR.exists():
        shutil.rmtree(SNAPSHOT_DIR)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def snapshot_step(
    *,
    step_index: int,
    source: str,
    payload: dict[str, Any],
    response: dict[str, Any],
) -> None:
    step_dir = SNAPSHOT_DIR / f"{step_index:03d}_{source}"
    step_dir.mkdir(parents=True, exist_ok=True)

    write_json(step_dir / "payload.json", normalize(payload))
    write_json(step_dir / "response.json", compact(response))

    image = response.get("image")
    if isinstance(image, dict):
        image_data = image.get("data")
        if isinstance(image_data, str):
            screenshot = decode_png_base64(image_data)
            (step_dir / "screenshot.png").write_bytes(screenshot)

    a11y_tree = response.get("text")
    if isinstance(a11y_tree, str):
        (step_dir / "a11y_tree.txt").write_text(a11y_tree, encoding="utf-8")


def snapshot_reward(
    *,
    step_index: int,
    payload: dict[str, Any],
    response: dict[str, Any],
) -> None:
    step_dir = SNAPSHOT_DIR / f"{step_index:03d}_reward"
    step_dir.mkdir(parents=True, exist_ok=True)

    write_json(step_dir / "payload.json", normalize(payload))
    write_json(step_dir / "reward.json", compact(response))


def snapshot_final(final_text: str, trace: list[dict[str, Any]]) -> None:
    write_json(SNAPSHOT_DIR / "trace.json", trace)
    (SNAPSHOT_DIR / "final.txt").write_text(final_text + "\n", encoding="utf-8")


def build_trajectory_input(state: dict[str, Any]) -> list[dict[str, Any]]:
    latest_a11y = state["observations"][-1]["a11y_tree"] if state["observations"] else ""

    content: list[dict[str, Any]] = [
        {
            "type": "input_text",
            "text": (
                f"Task: {state['task_name']}\n"
                "Solve this WebGym task end-to-end using tools.\n"
                "Always use the screenshot and accessibility tree to decide actions.\n"
                "Do not use any hard-coded button coordinate from the test harness.\n"
                "Call webgym_start first. Then call webgym_action until complete. "
                "After DONE, call webgym_reward.\n"
                "If reward is 1.0, final answer must be exactly: PASS reward=1.0\n\n"
                f"Latest accessibility tree:\n{latest_a11y or '(none yet)'}"
            ),
        }
    ]

    for obs in state["observations"][-MAX_TRAJECTORY_IMAGES:]:
        content.append(
            {
                "type": "input_text",
                "text": f"Trajectory screenshot {obs['index']} after {obs['source']}:",
            }
        )
        content.append(
            {
                "type": "input_image",
                "image_url": f"data:image/png;base64,{obs['image_data']}",
            }
        )

    return [{"role": "user", "content": content}]


def clean_action(action: Any) -> dict[str, Any]:
    if not isinstance(action, dict):
        raise AssertionError(f"action must be an object: {action!r}")

    action_type = action.get("action_type")
    if not isinstance(action_type, str):
        raise AssertionError(f"action_type must be a string: {action!r}")

    allowed_fields = ACTION_ALLOWED_FIELDS.get(action_type)
    if allowed_fields is None:
        raise AssertionError(f"unsupported action_type: {action_type}")

    return {key: value for key, value in action.items() if key in allowed_fields}


def clean_actions(actions: Any) -> list[dict[str, Any]]:
    if not isinstance(actions, list):
        raise AssertionError(f"actions must be a list: {actions!r}")

    return [clean_action(action) for action in actions]


def execute_tool_call(name: str, args: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    if name == "webgym_start":
        payload = {
            "op": "start",
            "session_id": SESSION_ID,
            "task_id": TASK_ID,
            "include_a11y": True,
        }

    elif name == "webgym_action":
        actions = clean_actions(args.get("actions"))
        payload = {
            "op": "action",
            "session_id": SESSION_ID,
            "task_id": TASK_ID,
            "include_a11y": True,
            "actions": actions,
        }

    elif name == "webgym_reward":
        payload = {
            "op": "reward",
            "session_id": SESSION_ID,
            "task_id": TASK_ID,
        }

    else:
        raise AssertionError(f"unexpected tool: {name}")

    response = post_env(payload)
    step_index = len(state["trace"]) + 1
    compact_response = compact(response)

    state["trace"].append(
        {
            "step": step_index,
            "tool": name,
            "payload": normalize(payload),
            "response": compact_response,
        }
    )

    if name == "webgym_reward":
        snapshot_reward(
            step_index=step_index,
            payload=payload,
            response=response,
        )
    else:
        snapshot_step(
            step_index=step_index,
            source=name,
            payload=payload,
            response=response,
        )

    if "image" in response:
        image_data = response["image"]["data"]
        decode_png_base64(image_data)

        state["observations"].append(
            {
                "index": len(state["observations"]) + 1,
                "source": name,
                "a11y_tree": response.get("text") or "",
                "image_data": image_data,
            }
        )

        state["observations"] = state["observations"][-MAX_TRAJECTORY_IMAGES:]

    if name == "webgym_action":
        actions = payload["actions"]
        if any(action.get("action_type") in {"DONE", "FAIL"} for action in actions):
            state["terminal_requested"] = True

    if name == "webgym_reward":
        state["reward"] = response.get("reward")

    return compact(response)


def run_gpt_tool_loop() -> tuple[list[dict[str, Any]], str]:
    reset_snapshot_dir()

    client = openai_client()

    state: dict[str, Any] = {
        "task_name": TASK_NAME,
        "observations": [],
        "trace": [],
        "terminal_requested": False,
        "reward": None,
    }

    conversation: list[Any] = []

    for _ in range(MAX_AGENT_STEPS):
        response = client.responses.create(
            model=MODEL,
            input=conversation + build_trajectory_input(state),
            tools=TOOLS,
            tool_choice="required",
            parallel_tool_calls=False,
        )

        conversation += response.output
        calls = function_calls(response.output)

        if len(calls) != 1:
            raise AssertionError(f"expected exactly one tool call, got {len(calls)}")

        call = calls[0]
        args = json.loads(str(call.arguments or "{}"))
        tool_result = execute_tool_call(str(call.name), args, state)

        conversation.append(
            {
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": json.dumps(tool_result),
            }
        )

        if state["reward"] is not None:
            final = client.responses.create(
                model=MODEL,
                input=conversation
                + build_trajectory_input(state)
                + [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": (
                                    f"Reward is {state['reward']}. "
                                    "If reward is 1.0, respond exactly: PASS reward=1.0"
                                ),
                            }
                        ],
                    }
                ],
            )
            final_text = final.output_text.strip()
            snapshot_final(final_text, state["trace"])
            return state["trace"], final_text

    raise AssertionError("model did not finish within step budget")


def post_env(payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        GATEWAY_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
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


def normalize(value: Any) -> Any:
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if key == "session_id":
                normalized[key] = "<session_id>"
            elif key == "data" and isinstance(item, str) and len(item) > 256:
                normalized[key] = f"<redacted:{len(item)} chars>"
            else:
                normalized[key] = normalize(item)
        return normalized

    if isinstance(value, list):
        return [normalize(item) for item in value]

    return value


def compact(value: Any) -> dict[str, Any]:
    normalized = normalize(value)
    if not isinstance(normalized, dict):
        raise AssertionError(f"expected dict response, got: {type(normalized)}")
    return normalized


def function_calls(output: Any) -> list[Any]:
    return [
        cast(Any, item)
        for item in output
        if getattr(item, "type", None) == "function_call"
    ]


def openai_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is required for this test")
    return OpenAI(api_key=OPENAI_API_KEY)


def validate_trace(trace: list[dict[str, Any]], final_text: str) -> None:
    if not trace:
        raise AssertionError("empty GPT tool trace")

    if trace[0]["payload"].get("op") != "start":
        raise AssertionError(f"first tool must start the environment: {trace[0]}")

    for item in trace:
        payload = item["payload"]
        if payload.get("op") in {"start", "action"}:
            if payload.get("include_a11y") is not True:
                raise AssertionError(f"include_a11y must always be true: {payload}")

    if not any(
        payload.get("op") == "action"
        and any(action.get("action_type") == "DONE" for action in payload.get("actions", []))
        for payload in (item["payload"] for item in trace)
    ):
        raise AssertionError("model never sent DONE")

    reward_calls = [item for item in trace if item["payload"].get("op") == "reward"]
    if len(reward_calls) != 1:
        raise AssertionError(f"expected one reward call, got {len(reward_calls)}")

    reward = reward_calls[0]["response"].get("reward")
    if reward != 1.0:
        raise AssertionError(f"expected reward=1.0, got {reward}")

    if final_text != "PASS reward=1.0":
        raise AssertionError(f"unexpected final text: {final_text!r}")


def has_terminal_action(trace: list[dict[str, Any]]) -> bool:
    for item in trace:
        payload = item["payload"]
        if payload.get("op") != "action":
            continue

        for action in payload.get("actions", []):
            if action.get("action_type") in {"DONE", "FAIL"}:
                return True

    return False


def has_started_session(trace: list[dict[str, Any]]) -> bool:
    return any(
        item["payload"].get("op") == "start"
        and item["response"].get("status") == "ok"
        for item in trace
    )


def cleanup_session() -> None:
    try:
        post_env(
            {
                "op": "action",
                "session_id": SESSION_ID,
                "task_id": TASK_ID,
                "actions": [{"action_type": "FAIL"}],
            }
        )
    except Exception as exc:
        print(f"cleanup failed: {exc}", file=sys.stderr)


def main() -> None:
    trace: list[dict[str, Any]] = []

    try:
        trace, final_text = run_gpt_tool_loop()
        validate_trace(trace, final_text)
        print("gpt e2e test pass")
        print(f"snapshot dir: {SNAPSHOT_DIR}")
    finally:
        if has_started_session(trace) and not has_terminal_action(trace):
            cleanup_session()


if __name__ == "__main__":
    main()
