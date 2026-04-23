from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class ActionType(str, Enum):
    MOVE_TO = "MOVE_TO"
    CLICK = "CLICK"
    MOUSE_DOWN = "MOUSE_DOWN"
    MOUSE_UP = "MOUSE_UP"
    RIGHT_CLICK = "RIGHT_CLICK"
    DOUBLE_CLICK = "DOUBLE_CLICK"
    DRAG_TO = "DRAG_TO"
    SCROLL = "SCROLL"
    TYPING = "TYPING"
    PRESS = "PRESS"
    KEY_DOWN = "KEY_DOWN"
    KEY_UP = "KEY_UP"
    HOTKEY = "HOTKEY"
    WAIT = "WAIT"
    FAIL = "FAIL"
    DONE = "DONE"


class BaseComputerAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_type: ActionType

    @property
    def parameters(self) -> dict[str, Any]:
        return self.model_dump(exclude={"action_type"})


class MoveToAction(BaseComputerAction):
    action_type: Literal[ActionType.MOVE_TO]
    x: int
    y: int


class ClickAction(BaseComputerAction):
    action_type: Literal[ActionType.CLICK]
    button: str
    x: int
    y: int
    num_clicks: int


class MouseDownAction(BaseComputerAction):
    action_type: Literal[ActionType.MOUSE_DOWN]
    button: str


class MouseUpAction(BaseComputerAction):
    action_type: Literal[ActionType.MOUSE_UP]
    button: str


class RightClickAction(BaseComputerAction):
    action_type: Literal[ActionType.RIGHT_CLICK]
    x: int
    y: int


class DoubleClickAction(BaseComputerAction):
    action_type: Literal[ActionType.DOUBLE_CLICK]
    x: int
    y: int


class DragToAction(BaseComputerAction):
    action_type: Literal[ActionType.DRAG_TO]
    x: int
    y: int


class ScrollAction(BaseComputerAction):
    action_type: Literal[ActionType.SCROLL]
    dx: int
    dy: int


class TypingAction(BaseComputerAction):
    action_type: Literal[ActionType.TYPING]
    text: str


class PressAction(BaseComputerAction):
    action_type: Literal[ActionType.PRESS]
    key: str


class KeyDownAction(BaseComputerAction):
    action_type: Literal[ActionType.KEY_DOWN]
    key: str


class KeyUpAction(BaseComputerAction):
    action_type: Literal[ActionType.KEY_UP]
    key: str


class HotkeyAction(BaseComputerAction):
    action_type: Literal[ActionType.HOTKEY]
    keys: list[str]


class WaitAction(BaseComputerAction):
    action_type: Literal[ActionType.WAIT]


class FailAction(BaseComputerAction):
    action_type: Literal[ActionType.FAIL]


class DoneAction(BaseComputerAction):
    action_type: Literal[ActionType.DONE]


ComputerAction = Annotated[
    Union[
        MoveToAction,
        ClickAction,
        MouseDownAction,
        MouseUpAction,
        RightClickAction,
        DoubleClickAction,
        DragToAction,
        ScrollAction,
        TypingAction,
        PressAction,
        KeyDownAction,
        KeyUpAction,
        HotkeyAction,
        WaitAction,
        FailAction,
        DoneAction,
    ],
    Field(discriminator="action_type"),
]
