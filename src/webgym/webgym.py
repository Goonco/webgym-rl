import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Dict

from environment.webgym.webgym.environment.process_isolator import ProcessBasedHttpStack
from src.schemas.computer_action import (
    ActionType,
    ClickAction,
    ComputerAction,
    DoneAction,
    DragToAction,
    FailAction,
    HotkeyAction,
    KeyDownAction,
    MouseDownAction,
    MouseUpAction,
    MoveToAction,
    PressAction,
    ScrollAction,
    TypingAction,
    WaitAction,
)
from src.schemas.config import HttpStackConfig, OmniboxConfig
from src.schemas.omnibox import OmniboxInstance
from src.schemas.request import ActionRequest, Request, RequestAdapter, RewardRequest, StartRequest
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
    def __init__(
        self,
        task_store: TaskStore,
        httpstack_config: HttpStackConfig,
        omnibox_config: OmniboxConfig,
    ) -> None:
        self.task_store = task_store

        # wait_timeout and timeout (operation_timeout) is not used
        self.http_stack = ProcessBasedHttpStack(
            pool_config=httpstack_config.get_pool_dict(),
        )

        self.httpstack_config = httpstack_config
        self.omnibox_config = omnibox_config

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
        request = RequestAdapter.validate_python(request)

        deadline = RequestDeadline(deadline_at)
        if isinstance(request, StartRequest):
            return self._handle_start(request, deadline)
        if isinstance(request, ActionRequest):
            return self._handle_action(request, deadline)
        if isinstance(request, RewardRequest):
            return self._handle_reward(request)

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
        terminal_action = None

        try:
            for action in request.actions:
                action_type = action.action_type

                for command in self._browser_commands_for_action(action):
                    self._execute_browser_command(instance, command, deadline)

                if action_type == ActionType.FAIL:
                    terminal_action = ActionType.FAIL
                    self.reward_cache[session_id] = 0.0
                elif action_type == ActionType.DONE:
                    terminal_action = ActionType.DONE
                    task = self.task_store.get(task_id)
                    self.reward_cache[session_id] = self._evaluate(task, instance, deadline)
                    break

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
            if terminal_action is not None:
                released_instance = self.session_map.pop(session_id, None)
                if released_instance is not None:
                    self._schedule_release(
                        released_instance,
                        task_id=task_id,
                        reason=f"terminal_{terminal_action.value.lower()}",
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

        timeout = self.httpstack_config.release.timeout
        deadline = RequestDeadline(time.monotonic() + timeout)
        return self.http_stack.single_execute(
            func=reset_instance,
            host=self.omnibox_config.host,
            port=self.omnibox_config.master_port,
            api_key=self.omnibox_config.api_key,
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

    def _browser_commands_for_action(self, action: ComputerAction) -> list[dict]:
        if isinstance(action, MoveToAction):
            return [{"hover_coords": {"x": action.x, "y": action.y}}]

        if isinstance(action, ScrollAction):
            return [{"scroll_pointer": {"dx": action.dx, "dy": action.dy}}]

        if isinstance(action, TypingAction):
            return [
                {"keypress": {"keys": [key]}} for key in self._text_to_key_sequence(action.text)
            ]

        if isinstance(action, HotkeyAction):
            return [{"keypress": {"keys": action.keys}}]

        #####################
        # Single Key Action #
        #####################

        if isinstance(action, (PressAction, KeyDownAction, KeyDownAction)):
            return [{"keypress": {"keys": [action.key]}}]

        ################
        # Mouse Action #
        ################

        if isinstance(action, ClickAction):
            return [
                {"click_coords": {"x": action.x, "y": action.y, "button": action.button}}
                for _ in range(action.num_clicks)
            ]

        if isinstance(action, MouseDownAction):
            raise ValueError("MOUSE_DOWN is not supported by the current Omnibox command API")

        if isinstance(action, MouseUpAction):
            raise ValueError("MOUSE_UP is not supported by the current Omnibox command API")

        if isinstance(action, DragToAction):
            raise ValueError("DRAG_TO is not supported by the current Omnibox command API")

        ###############
        # Void Action #
        ###############

        if isinstance(action, WaitAction):
            return [{"sleep": {"duration": 1.0}}]

        if isinstance(action, (DoneAction, FailAction)):
            return []

        # for return type inference
        raise Exception

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
        return self.http_stack.single_execute(
            func=execute_browser_command,
            host=self.omnibox_config.host,
            port=self.omnibox_config.master_port,
            api_key=self.omnibox_config.api_key,
            instance=instance,
            command=command,
            check_timeout=deadline.check,
            timeout=deadline.timeout(self.httpstack_config.execute.timeout),
        )

    def _allocate_instance(self, deadline: RequestDeadline):
        backoffs = self._backoff_delays()
        while True:
            deadline.check("_allocate_instance")
            # TODO allocate 성공 이후 남은 거 할 시간 너무 없는경우에 대한 처리 필요

            try:
                return self.http_stack.single_execute(
                    func=allocate_instance,
                    host=self.omnibox_config.host,
                    port=self.omnibox_config.master_port,
                    api_key=self.omnibox_config.api_key,
                    check_timeout=deadline.check,
                    timeout=deadline.timeout(self.httpstack_config.allocate.timeout),
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
                return self.http_stack.single_execute(
                    func=navigate,
                    host=self.omnibox_config.host,
                    port=self.omnibox_config.master_port,
                    api_key=self.omnibox_config.api_key,
                    url=url,
                    instance=instance,
                    check_timeout=deadline.check,
                    timeout=deadline.timeout(self.httpstack_config.navigate.timeout),
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
                return self.http_stack.single_execute(
                    func=screenshot,
                    host=self.omnibox_config.host,
                    port=self.omnibox_config.master_port,
                    api_key=self.omnibox_config.api_key,
                    instance=instance,
                    check_timeout=deadline.check,
                    timeout=deadline.timeout(self.httpstack_config.screenshot.timeout),
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
                return self.http_stack.single_execute(
                    func=get_interactive_tree,
                    host=self.omnibox_config.host,
                    port=self.omnibox_config.master_port,
                    api_key=self.omnibox_config.api_key,
                    instance=instance,
                    check_timeout=deadline.check,
                    timeout=deadline.timeout(self.httpstack_config.screenshot.timeout),
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
                return self.http_stack.single_execute(
                    func=get_page_snapshot,
                    host=self.omnibox_config.host,
                    port=self.omnibox_config.master_port,
                    api_key=self.omnibox_config.api_key,
                    instance=instance,
                    selectors=selectors,
                    include_html=include_html,
                    check_timeout=deadline.check,
                    timeout=deadline.timeout(self.httpstack_config.execute.timeout),
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
