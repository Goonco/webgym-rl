import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Dict

from webgym.environment.process_isolator import ProcessBasedHttpStack

from src.config import WebGymConfig
from src.schemas.computer_action import ActionType
from src.schemas.omnibox import OmniboxInstance
from src.schemas.request import ActionRequest, Request, RewardRequest, StartRequest
from src.schemas.response import ActionResponse, ImagePayload, RewardResponse
from src.task_store import TaskStore
from src.webgym.error import WebGymEnvRetryableError
from src.webgym.pickleable_http_functions import (
    allocate_instance,
    execute_browser_command,
    get_interactive_tree,
    get_page_snapshot,
    navigate,
    reset_instance,
    screenshot,
)
from src.webgym.rule_evaluator import (
    collect_selectors,
    evaluate_page_rules,
    uses_page_html,
)


class DeadlineExceeded(TimeoutError):
    pass


class RequestDeadline:
    def __init__(self, deadline_at: float) -> None:
        self.deadline_at = deadline_at

    def remaining(self) -> float:
        return self.deadline_at - time.monotonic()

    def check(self, context: str) -> None:
        if self.remaining() <= 0:
            raise DeadlineExceeded(f"Gateway request deadline exceeded in {context}")

    def timeout(self, cap: float) -> float:
        remaining = self.remaining()
        if remaining <= 0:
            raise DeadlineExceeded("Gateway request deadline exceeded")
        return min(cap, remaining)


@dataclass(order=True)
class ReleaseJob:
    run_at: float
    attempt: int = field(compare=False)
    instance: OmniboxInstance = field(compare=False)
    task_id: str | None = field(default=None, compare=False)
    reason: str = field(default="", compare=False)


class WebGym:
    def __init__(self, task_store: TaskStore, config: WebGymConfig) -> None:
        self.task_store = task_store

        # wait_timeout and timeout (operation_timeout) is not used
        self.http_stack = ProcessBasedHttpStack(
            pool_config=config.httpstack_config.get_pool_dit(),
        )

        self.config = config
        self.session_map: dict[int, OmniboxInstance] = {}
        self.reward_cache: Dict[int, float] = {}

        self.BACKOFF_MAX_SEC = 8
        self.RELEASE_BACKOFF_MAX_SEC = 60

        self.release_queue: queue.PriorityQueue[ReleaseJob] = queue.PriorityQueue()
        self.release_stop = threading.Event()
        self.release_thread: threading.Thread | None = None
        self.release_lock = threading.Lock()
        self.release_pending_keys: set[tuple[str, str]] = set()

    def open(self) -> None:
        self.http_stack.start()
        self._start_release_worker()

    def close(self) -> None:
        self._stop_release_worker()
        self.http_stack.stop()

    def handle_request(self, request: Request, deadline_at: float):
        deadline = RequestDeadline(deadline_at)
        if isinstance(request, StartRequest):
            response = self._handle_start(request, deadline)
        elif isinstance(request, ActionRequest):
            response = self._handle_action(request, deadline)
        elif isinstance(request, RewardRequest):
            response = self._handle_reward(request)
        else:
            raise TypeError(f"Unsupported request type: {type(request).__name__}")

        return response

    def _handle_start(self, request: StartRequest, deadline: RequestDeadline) -> ActionResponse:
        session_id = request.session_id
        task_id = request.task_id
        if session_id in self.session_map:
            raise ValueError("Duplice request_id")

        instance = None
        task = self.task_store.get(task_id)
        try:
            instance = self._allocate_instance(deadline)
            self._navigate(instance, task.website, deadline)
            screenshot = self._screenshot(instance, deadline)

            text = None
            if request.include_a11y:
                text = self._a11y_tree(instance, deadline)

            self.session_map[session_id] = instance
            return ActionResponse(
                session_id=session_id,
                task_id=task_id,
                text=text,
                image=ImagePayload(data=screenshot, mimeType="image/png"),
            )

        except Exception:
            if instance is not None:
                self.session_map.pop(session_id, None)
                self._schedule_release(
                    instance,
                    task_id=task_id,
                    reason="start_setup_failed",
                )
            raise

    def _handle_action(
        self,
        request: ActionRequest,
        deadline: RequestDeadline,
    ) -> ActionResponse:
        session_id = request.session_id
        task_id = request.task_id
        if session_id not in self.session_map:
            raise KeyError(f"Unknown session_id: {session_id}")

        instance = self.session_map[session_id]
        terminal_action_type = self._terminal_action_type(request.actions)

        try:
            for action in request.actions:
                for command in self._browser_commands_for_action(action):
                    self._execute_browser_command(instance, command, deadline)

            if terminal_action_type == ActionType.FAIL:
                self.reward_cache[session_id] = 0.0
            elif terminal_action_type == ActionType.DONE:
                task = self.task_store.get(task_id)
                self.reward_cache[session_id] = self._evaluate(task, instance, deadline)

            screenshot = self._screenshot(instance, deadline)
            text = None
            if request.include_a11y:
                text = self._a11y_tree(instance, deadline)

            return ActionResponse(
                session_id=session_id,
                task_id=task_id,
                text=text,
                image=ImagePayload(data=screenshot, mimeType="image/png"),
            )
        finally:
            if terminal_action_type is not None:
                released_instance = self.session_map.pop(session_id, None)
                if released_instance is not None:
                    self._schedule_release(
                        released_instance,
                        task_id=task_id,
                        reason=f"terminal_{terminal_action_type.value.lower()}",
                    )

    def _handle_reward(
        self,
        request: RewardRequest,
    ) -> RewardResponse:
        reward = self.reward_cache.pop(request.session_id, 0.0)

        return RewardResponse(
            session_id=request.session_id,
            task_id=request.task_id,
            reward=reward,
        )

    def _terminal_action_type(self, actions) -> ActionType | None:
        terminal_action_type = None
        for action in actions:
            if action.action_type in {ActionType.DONE, ActionType.FAIL}:
                terminal_action_type = action.action_type
        return terminal_action_type

    def _evaluate(self, task, instance: OmniboxInstance, deadline: RequestDeadline) -> float:
        if task.evaluation is None:
            print(f"Rule evaluation for task {task.task_id}: reward=0.0 (no rules)")
            return 0.0

        try:
            selectors = collect_selectors(task.evaluation)
            snapshot = self._page_snapshot(
                instance,
                selectors=selectors,
                include_html=uses_page_html(task.evaluation),
                deadline=deadline,
            )
            result = evaluate_page_rules(task.evaluation, snapshot)
            print(
                f"Rule evaluation for task {task.task_id}: "
                f"reward={result.reward} ({result.summary()})"
            )
            return result.reward
        except DeadlineExceeded:
            raise
        except Exception as exc:
            print(f"Rule evaluation for task {task.task_id} failed: {exc}")
            return 0.0

    def _start_release_worker(self) -> None:
        if self.release_thread is not None and self.release_thread.is_alive():
            return

        self.release_stop.clear()
        self.release_thread = threading.Thread(
            target=self._release_worker_loop,
            name="webgym-release-worker",
            daemon=True,
        )
        self.release_thread.start()

    def _stop_release_worker(self) -> None:
        self.release_stop.set()
        if self.release_thread is not None:
            self.release_thread.join(timeout=5.0)
            self.release_thread = None

    def _schedule_release(
        self,
        instance: OmniboxInstance,
        task_id: str | None = None,
        reason: str = "",
        attempt: int = 0,
        delay: float = 0.0,
    ) -> None:
        key = self._release_key(instance)
        run_at = time.monotonic() + delay

        with self.release_lock:
            if key in self.release_pending_keys:
                return
            self.release_pending_keys.add(key)

        self.release_queue.put(
            ReleaseJob(
                run_at=run_at,
                attempt=attempt,
                instance=instance,
                task_id=task_id,
                reason=reason,
            )
        )

    def _release_worker_loop(self) -> None:
        while not self.release_stop.is_set():
            self._release_worker_loop_once(timeout=1.0)

    def _release_worker_loop_once(self, timeout: float = 1.0) -> bool:
        try:
            job = self.release_queue.get(timeout=timeout)
        except queue.Empty:
            return False

        now = time.monotonic()
        if job.run_at > now:
            self.release_queue.put(job)
            self.release_queue.task_done()
            wait_for = min(job.run_at - now, 1.0)
            if wait_for > 0:
                self.release_stop.wait(wait_for)
            return False

        try:
            self._release_once(job.instance)
        except Exception as exc:
            if self._is_already_released_error(exc):
                self._mark_release_done(job.instance)
            else:
                self._reschedule_release(job)
        else:
            self._mark_release_done(job.instance)
        finally:
            self.release_queue.task_done()

        return True

    def _reschedule_release(self, job: ReleaseJob) -> None:
        next_attempt = job.attempt + 1
        self.release_queue.put(
            ReleaseJob(
                run_at=time.monotonic() + self._release_backoff(job.attempt),
                attempt=next_attempt,
                instance=job.instance,
                task_id=job.task_id,
                reason=job.reason,
            )
        )

    def _release_once(self, instance: OmniboxInstance):
        config = self.config
        timeout = config.httpstack_config.release.timeout
        deadline = RequestDeadline(time.monotonic() + timeout)
        return self.http_stack.single_execute(
            func=reset_instance,
            host=config.omnibox_host,
            port=config.omnibox_port,
            api_key=config.omnibox_api_key,
            instance=instance,
            check_timeout=deadline.check,
            timeout=timeout,
        )

    def _mark_release_done(self, instance: OmniboxInstance) -> None:
        with self.release_lock:
            self.release_pending_keys.discard(self._release_key(instance))

    def _release_key(self, instance: OmniboxInstance) -> tuple[str, str]:
        return (str(instance.get("node", "")), str(instance.get("instance_id", "")))

    def _release_backoff(self, attempt: int) -> float:
        return min(2**attempt, self.RELEASE_BACKOFF_MAX_SEC)

    def _is_already_released_error(self, exc: Exception) -> bool:
        error = str(exc).lower()
        return any(
            pattern in error
            for pattern in (
                "invalid instance uuid",
                "invalid uuid",
                "instance not found",
                "does not exist",
                "not found",
                "not in use",
                "already released",
            )
        )

    def _browser_commands_for_action(self, action) -> list[dict]:
        action_type = action.action_type

        if action_type == ActionType.MOVE_TO:
            return [{"hover_coords": {"x": action.x, "y": action.y}}]

        if action_type == ActionType.CLICK:
            if action.button.lower() != "left":
                raise ValueError(f"Unsupported CLICK button: {action.button}")
            num_clicks = max(1, int(action.num_clicks))
            return [{"click_coords": {"x": action.x, "y": action.y}} for _ in range(num_clicks)]

        if action_type == ActionType.RIGHT_CLICK:
            raise ValueError("RIGHT_CLICK is not supported by the current Omnibox command API")

        if action_type == ActionType.DOUBLE_CLICK:
            return [
                {"click_coords": {"x": action.x, "y": action.y}},
                {"click_coords": {"x": action.x, "y": action.y}},
            ]

        if action_type == ActionType.MOUSE_DOWN:
            raise ValueError("MOUSE_DOWN is not supported by the current Omnibox command API")

        if action_type == ActionType.MOUSE_UP:
            raise ValueError("MOUSE_UP is not supported by the current Omnibox command API")

        if action_type == ActionType.DRAG_TO:
            raise ValueError("DRAG_TO is not supported by the current Omnibox command API")

        if action_type == ActionType.SCROLL:
            if action.dy < 0:
                return [{"page_up": {"amount": abs(action.dy), "full_page": False}}]
            if action.dy > 0:
                return [{"page_down": {"amount": abs(action.dy), "full_page": False}}]
            if action.dx < 0:
                return [{"hover_and_scroll_coords": {"x": 640, "y": 384, "direction": "left"}}]
            if action.dx > 0:
                return [{"hover_and_scroll_coords": {"x": 640, "y": 384, "direction": "right"}}]
            return [{"sleep": {"duration": 0.1}}]

        if action_type == ActionType.TYPING:
            return [
                {"keypress": {"keys": [key]}} for key in self._text_to_key_sequence(action.text)
            ]

        if action_type == ActionType.PRESS:
            return [{"keypress": {"keys": [action.key]}}]

        if action_type == ActionType.KEY_DOWN:
            return [{"keypress": {"keys": [action.key]}}]

        if action_type == ActionType.KEY_UP:
            return [{"keypress": {"keys": [action.key]}}]

        if action_type == ActionType.HOTKEY:
            return [{"keypress": {"keys": action.keys}}]

        if action_type == ActionType.WAIT:
            return [{"sleep": {"duration": 1.0}}]

        if action_type in {ActionType.DONE, ActionType.FAIL}:
            return []

        raise ValueError(f"Unsupported action_type: {action_type}")

    def _text_to_key_sequence(self, text: str) -> list[str]:
        keys = []
        for char in text:
            if char == " ":
                keys.append("space")
            elif char == "\n":
                keys.append("enter")
            elif char == "\t":
                keys.append("tab")
            else:
                keys.append(char)
        return keys

    def _execute_browser_command(
        self,
        instance: OmniboxInstance,
        command: dict,
        deadline: RequestDeadline,
    ):
        deadline.check("_execute_browser_command")
        config = self.config
        return self.http_stack.single_execute(
            func=execute_browser_command,
            host=config.omnibox_host,
            port=config.omnibox_port,
            api_key=config.omnibox_api_key,
            instance=instance,
            command=command,
            check_timeout=deadline.check,
            timeout=deadline.timeout(config.httpstack_config.execute.timeout),
        )

    def _allocate_instance(self, deadline: RequestDeadline):
        backoffs = self._backoff_delays()
        while True:
            deadline.check("_allocate_instance")
            # TODO allocate 성공 이후 남은 거 할 시간 너무 없는경우에 대한 처리 필요

            try:
                config = self.config
                return self.http_stack.single_execute(
                    func=allocate_instance,
                    host=config.omnibox_host,
                    port=config.omnibox_port,
                    api_key=config.omnibox_api_key,
                    check_timeout=deadline.check,
                    timeout=deadline.timeout(config.httpstack_config.allocate.timeout),
                )

            except Exception as exc:
                if isinstance(exc, WebGymEnvRetryableError):
                    sleep_for = min(next(backoffs), max(0.0, deadline.remaining()))
                    if sleep_for <= 0:
                        raise DeadlineExceeded("Allocation deadline exceeded") from exc
                    time.sleep(sleep_for)
                else:
                    raise

    def _navigate(self, instance: OmniboxInstance, url: str, deadline: RequestDeadline):
        backoffs = self._backoff_delays()
        while True:
            deadline.check("_navigate")

            try:
                config = self.config
                return self.http_stack.single_execute(
                    func=navigate,
                    host=config.omnibox_host,
                    port=config.omnibox_port,
                    api_key=config.omnibox_api_key,
                    url=url,
                    instance=instance,
                    check_timeout=deadline.check,
                    timeout=deadline.timeout(config.httpstack_config.navigate.timeout),
                )
            except Exception as exc:
                if isinstance(exc, WebGymEnvRetryableError):
                    sleep_for = min(next(backoffs), max(0.0, deadline.remaining()))
                    if sleep_for <= 0:
                        raise DeadlineExceeded("Allocation deadline exceeded") from exc
                    time.sleep(sleep_for)
                else:
                    raise

    def _screenshot(self, instance: OmniboxInstance, deadline: RequestDeadline) -> str:
        backoffs = self._backoff_delays()
        while True:
            deadline.check("_screenshot")

            try:
                config = self.config
                return self.http_stack.single_execute(
                    func=screenshot,
                    host=config.omnibox_host,
                    port=config.omnibox_port,
                    api_key=config.omnibox_api_key,
                    instance=instance,
                    check_timeout=deadline.check,
                    timeout=deadline.timeout(config.httpstack_config.screenshot.timeout),
                )

            except Exception as exc:
                if isinstance(exc, WebGymEnvRetryableError):
                    sleep_for = min(next(backoffs), max(0.0, deadline.remaining()))
                    if sleep_for <= 0:
                        raise DeadlineExceeded("Allocation deadline exceeded") from exc
                    time.sleep(sleep_for)
                else:
                    raise

    def _a11y_tree(self, instance: OmniboxInstance, deadline: RequestDeadline):
        backoffs = self._backoff_delays()
        while True:
            deadline.check("_a11y_tree")

            try:
                config = self.config
                return self.http_stack.single_execute(
                    func=get_interactive_tree,
                    host=config.omnibox_host,
                    port=config.omnibox_port,
                    api_key=config.omnibox_api_key,
                    instance=instance,
                    check_timeout=deadline.check,
                    timeout=deadline.timeout(config.httpstack_config.screenshot.timeout),
                )

            except Exception as exc:
                if isinstance(exc, WebGymEnvRetryableError):
                    sleep_for = min(next(backoffs), max(0.0, deadline.remaining()))
                    if sleep_for <= 0:
                        raise DeadlineExceeded("Allocation deadline exceeded") from exc
                    time.sleep(sleep_for)
                else:
                    raise

    def _page_snapshot(
        self,
        instance: OmniboxInstance,
        selectors: list[str],
        include_html: bool,
        deadline: RequestDeadline,
    ) -> dict:
        backoffs = self._backoff_delays()
        while True:
            deadline.check("_page_snapshot")

            try:
                config = self.config
                return self.http_stack.single_execute(
                    func=get_page_snapshot,
                    host=config.omnibox_host,
                    port=config.omnibox_port,
                    api_key=config.omnibox_api_key,
                    instance=instance,
                    selectors=selectors,
                    include_html=include_html,
                    check_timeout=deadline.check,
                    timeout=deadline.timeout(config.httpstack_config.execute.timeout),
                )

            except Exception as exc:
                if isinstance(exc, WebGymEnvRetryableError):
                    sleep_for = min(next(backoffs), max(0.0, deadline.remaining()))
                    if sleep_for <= 0:
                        raise DeadlineExceeded("Allocation deadline exceeded") from exc
                    time.sleep(sleep_for)
                else:
                    raise

    def _backoff_delays(self):
        """Generator for backoff secs"""
        delay = 1.0
        while True:
            yield delay
            delay = min(delay * 2, self.BACKOFF_MAX_SEC)
