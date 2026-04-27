import json
import shutil
from pathlib import Path
from typing import Any, cast

from openai import OpenAI

from src.task_store import TaskStore
from tests.util import (
    ACTION_ALLOWED_FIELDS,
    TOOLS,
    assert_ok_response,
    decode_png_base64,
    post,
)


class Runner:
    def __init__(
        self,
        *,
        task_id: str,
        session_id: int,
        config_path: Path,
        max_trajectory_images: int,
        max_steps: int,
        model: str,
        api_key: str,
    ) -> None:
        self.task_id = task_id
        self.session_id = session_id

        self.max_trajectory_images = max_trajectory_images
        self.max_steps = max_steps
        self.model = model

        self.client = OpenAI(api_key=api_key)

        here_dir = Path(__file__).resolve().parent
        self.base_dir = (here_dir / "../../").resolve()
        self.snapshot_dir = (
            self.base_dir / "tests" / "e2e_test" / "__snapshots__" / f"{task_id}-{session_id}"
        )

        with open(config_path, "r", encoding="utf-8") as f:
            config: dict[str, Any] = json.load(f)

        task_store = TaskStore.from_file(path=self.base_dir / f"./{config['task_file_path']}")
        task = task_store.get(self.task_id)
        self.task_name = task.instruction

        gateway = config["gateway"]
        self.url = f"http://{gateway['host']}:{gateway['port']}/v1/env"

    def run(self) -> tuple[list[dict[str, Any]], str]:
        trace: list[dict[str, Any]] = []

        try:
            trace, final_text = self._run_gpt_tool_loop()
            self._validate_trace(trace, final_text)

            print("gpt e2e test pass")
            print(f"snapshot dir: {self.snapshot_dir}")

            return trace, final_text

        finally:
            if self._has_started_session(trace) and not self._has_terminal_action(trace):
                self._cleanup_session()

    def _run_gpt_tool_loop(self) -> tuple[list[dict[str, Any]], str]:
        self._reset_snapshot_dir()

        state: dict[str, Any] = {
            "task_name": self.task_name,
            "observations": [],
            "trace": [],
            "reward": None,
        }

        conversation: list[Any] = []

        for _ in range(self.max_steps):
            response = self.client.responses.create(
                model=self.model,
                input=conversation + self._build_trajectory_input(state),
                tools=TOOLS,
                tool_choice="required",
                parallel_tool_calls=False,
            )

            conversation += response.output

            calls = self._function_calls(response.output)
            if len(calls) != 1:
                raise AssertionError(f"expected exactly one tool call, got {len(calls)}")

            call = calls[0]
            args = json.loads(str(call.arguments or "{}"))

            tool_result = self._execute_tool_call(
                name=str(call.name),
                args=args,
                state=state,
            )

            conversation.append(
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": json.dumps(tool_result),
                }
            )

        raise AssertionError("model did not finish within step budget")

    def _execute_tool_call(
        self,
        *,
        name: str,
        args: dict[str, Any],
        state: dict[str, Any],
    ) -> dict[str, Any]:
        if name == "webgym_start":
            payload = {
                "op": "start",
                "session_id": self.session_id,
                "task_id": self.task_id,
                "include_a11y": True,
            }

        elif name == "webgym_action":
            actions = self._clean_actions(args.get("actions"))

            payload = {
                "op": "action",
                "session_id": self.session_id,
                "task_id": self.task_id,
                "include_a11y": True,
                "actions": actions,
            }

        elif name == "webgym_reward":
            payload = {
                "op": "reward",
                "session_id": self.session_id,
                "task_id": self.task_id,
            }

        else:
            raise AssertionError(f"unexpected tool: {name}")

        response = self._post_env(payload)

        step_index = len(state["trace"]) + 1
        compact_response = self._compact(response)

        state["trace"].append(
            {
                "step": step_index,
                "tool": name,
                "payload": self._normalize(payload),
                "response": compact_response,
            }
        )

        if name == "webgym_reward":
            self._snapshot_reward(
                step_index=step_index,
                payload=payload,
                response=response,
            )
            state["reward"] = response.get("reward")

        else:
            self._snapshot_step(
                step_index=step_index,
                source=name,
                payload=payload,
                response=response,
            )

            image = response.get("image")
            if isinstance(image, dict):
                image_data = image.get("data")

                if isinstance(image_data, str):
                    decode_png_base64(image_data)

                    state["observations"].append(
                        {
                            "index": len(state["observations"]) + 1,
                            "source": name,
                            "a11y_tree": response.get("text") or "",
                            "image_data": image_data,
                        }
                    )

                    state["observations"] = state["observations"][-self.max_trajectory_images :]

        return self._compact(response)

    def _post_env(self, payload: dict[str, Any]) -> dict[str, Any]:
        response = post(self.url, payload)
        assert_ok_response(response, self.session_id, self.task_id)
        return response

    def _build_trajectory_input(self, state: dict[str, Any]) -> list[dict[str, Any]]:
        latest_a11y = state["observations"][-1]["a11y_tree"] if state["observations"] else ""

        content: list[dict[str, Any]] = [
            {
                "type": "input_text",
                "text": (
                    f"Task: {state['task_name']}\n"
                    "Solve this WebGym task end-to-end using tools.\n"
                    "Always use the latest screenshot and accessibility tree to decide actions.\n"
                    "Do not use any hard-coded button coordinate from the test harness.\n\n"
                    "Tool protocol:\n"
                    "- Call webgym_start first.\n"
                    "- Then call webgym_action until the task is complete.\n"
                    "- Each webgym_action may contain multiple actions; they are executed sequentially in the order provided.\n"
                    "- After the task is complete, send DONE with webgym_action.\n"
                    "- After DONE, call webgym_reward exactly once.\n"
                    "- If reward is 1.0, final answer must be exactly: PASS reward=1.0\n\n"
                    "Important action semantics:\n"
                    "- TYPING does not replace existing input text. It types into the currently focused field.\n"
                    "- If an input already contains a value, first CLICK the input, then select all text, then type the new value.\n"
                    "- To replace a value in an input, use this sequence:\n"
                    "  1. CLICK the target input.\n"
                    '  2. HOTKEY with keys ["ControlOrMeta", "a"].\n'
                    "  3. TYPING with the replacement text.\n"
                    "- For example, to replace a focused year field with 1975, use:\n"
                    '  {"action_type":"HOTKEY","keys":["ControlOrMeta","a"]}, '
                    '{"action_type":"TYPING","text":"1975"}\n'
                    "- If select-all is unreliable, delete the existing value with Backspace/Delete before typing.\n"
                    "- For forms with separate month/day/year fields, fill each field separately.\n"
                    "- Do not assume typing changed a value; verify using the next screenshot/accessibility tree.\n\n"
                    f"Latest accessibility tree:\n{latest_a11y or '(none yet)'}"
                ),
            }
        ]

        for obs in state["observations"][-self.max_trajectory_images :]:
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

    def _clean_action(self, action: Any) -> dict[str, Any]:
        if not isinstance(action, dict):
            raise AssertionError(f"action must be an object: {action!r}")

        action_type = action.get("action_type")
        if not isinstance(action_type, str):
            raise AssertionError(f"action_type must be a string: {action!r}")

        allowed_fields = ACTION_ALLOWED_FIELDS.get(action_type)
        if allowed_fields is None:
            raise AssertionError(f"unsupported action_type: {action_type}")

        return {key: value for key, value in action.items() if key in allowed_fields}

    def _clean_actions(self, actions: Any) -> list[dict[str, Any]]:
        if not isinstance(actions, list):
            raise AssertionError(f"actions must be a list: {actions!r}")

        return [self._clean_action(action) for action in actions]

    def _reset_snapshot_dir(self) -> None:
        if self.snapshot_dir.exists():
            shutil.rmtree(self.snapshot_dir)

        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

    def _snapshot_step(
        self,
        *,
        step_index: int,
        source: str,
        payload: dict[str, Any],
        response: dict[str, Any],
    ) -> None:
        step_dir = self.snapshot_dir / f"{step_index:03d}_{source}"
        step_dir.mkdir(parents=True, exist_ok=True)

        self._write_json(step_dir / "payload.json", self._normalize(payload))

        image = response.get("image")
        if isinstance(image, dict):
            image_data = image.get("data")
            if isinstance(image_data, str):
                screenshot = decode_png_base64(image_data)
                (step_dir / "screenshot.png").write_bytes(screenshot)

        a11y_tree = response.get("text")
        if isinstance(a11y_tree, str):
            (step_dir / "a11y_tree.txt").write_text(a11y_tree, encoding="utf-8")

    def _snapshot_reward(
        self,
        *,
        step_index: int,
        payload: dict[str, Any],
        response: dict[str, Any],
    ) -> None:
        step_dir = self.snapshot_dir / f"{step_index:03d}_reward"
        step_dir.mkdir(parents=True, exist_ok=True)

        self._write_json(step_dir / "payload.json", self._normalize(payload))
        self._write_json(step_dir / "reward.json", self._compact(response))

    def _snapshot_final(
        self,
        final_text: str,
        trace: list[dict[str, Any]],
    ) -> None:
        self._write_json(self.snapshot_dir / "trace.json", trace)
        (self.snapshot_dir / "final.txt").write_text(
            final_text + "\n",
            encoding="utf-8",
        )

    def _write_json(self, path: Path, value: Any) -> None:
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def _normalize(self, value: Any) -> Any:
        if isinstance(value, dict):
            normalized: dict[str, Any] = {}

            for key, item in value.items():
                if key == "session_id":
                    normalized[key] = "<session_id>"
                elif key == "data" and isinstance(item, str) and len(item) > 256:
                    normalized[key] = f"<redacted:{len(item)} chars>"
                else:
                    normalized[key] = self._normalize(item)

            return normalized

        if isinstance(value, list):
            return [self._normalize(item) for item in value]

        return value

    def _compact(self, value: Any) -> dict[str, Any]:
        normalized = self._normalize(value)

        if not isinstance(normalized, dict):
            raise AssertionError(f"expected dict response, got: {type(normalized)}")

        return normalized

    def _function_calls(self, output: Any) -> list[Any]:
        return [
            cast(Any, item) for item in output if getattr(item, "type", None) == "function_call"
        ]

    def _validate_trace(self, trace: list[dict[str, Any]], final_text: str) -> None:
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

    def _has_terminal_action(self, trace: list[dict[str, Any]]) -> bool:
        for item in trace:
            payload = item["payload"]

            if payload.get("op") != "action":
                continue

            for action in payload.get("actions", []):
                if action.get("action_type") in {"DONE", "FAIL"}:
                    return True

        return False

    def _has_started_session(self, trace: list[dict[str, Any]]) -> bool:
        return any(
            item["payload"].get("op") == "start" and item["response"].get("status") == "ok"
            for item in trace
        )

    def _cleanup_session(self) -> None:
        try:
            post(
                self.url,
                {
                    "op": "action",
                    "session_id": self.session_id,
                    "task_id": self.task_id,
                    "actions": [{"action_type": "FAIL"}],
                },
            )
        except Exception as exc:
            print(f"cleanup failed: {exc}")
