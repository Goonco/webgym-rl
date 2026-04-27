import base64
import json
import sys
import urllib.error
import urllib.request
from typing import Any, List, cast


def post(url: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
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


def assert_ok_response(response: dict, session_id, task_id) -> None:
    if response.get("status") != "ok":
        raise AssertionError(f"unexpected status: {response}")
    if response.get("session_id") != session_id:
        raise AssertionError(f"unexpected session_id: {response}")
    if response.get("task_id") != task_id:
        raise AssertionError(f"unexpected task_id: {response}")


def extract_function_calls(output: Any) -> list[Any]:
    return [cast(Any, item) for item in output if getattr(item, "type", None) == "function_call"]


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
