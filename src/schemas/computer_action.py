from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal, Optional, Union

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
    model_config = ConfigDict(frozen=True)

    action_type: ActionType

    @property
    def parameters(self) -> dict[str, Any]:
        return self.model_dump(exclude={"action_type"})


class MoveToAction(BaseComputerAction):
    action_type: Literal[ActionType.MOVE_TO]
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


class HotkeyAction(BaseComputerAction):
    action_type: Literal[ActionType.HOTKEY]
    keys: list[str]


###############
# Void Action #
###############


class WaitAction(BaseComputerAction):
    action_type: Literal[ActionType.WAIT]


class FailAction(BaseComputerAction):
    action_type: Literal[ActionType.FAIL]


class DoneAction(BaseComputerAction):
    action_type: Literal[ActionType.DONE]


#####################
# Single Key Action #
#####################


class PressAction(BaseComputerAction):
    action_type: Literal[ActionType.PRESS]
    key: str


class KeyDownAction(BaseComputerAction):
    action_type: Literal[ActionType.KEY_DOWN]
    key: str


class KeyUpAction(BaseComputerAction):
    action_type: Literal[ActionType.KEY_UP]
    key: str


################
# Mouse Action #
################


class MouseButtonType(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"


class _MouseAction(BaseComputerAction):
    button: MouseButtonType = MouseButtonType.LEFT


class MouseDownAction(_MouseAction):
    action_type: Literal[ActionType.MOUSE_DOWN]


class MouseUpAction(_MouseAction):
    action_type: Literal[ActionType.MOUSE_UP]


class ClickAction(_MouseAction):
    action_type: Literal[ActionType.CLICK]
    x: Optional[int] = None
    y: Optional[int] = None
    num_clicks: int = Field(default=1, ge=1)


class RightClickAction(ClickAction):
    action_type: Literal[ActionType.RIGHT_CLICK]
    button: Literal[MouseButtonType.RIGHT] = MouseButtonType.RIGHT
    num_clicks: int = 1


class DoubleClickAction(ClickAction):
    action_type: Literal[ActionType.DOUBLE_CLICK]
    button: Literal[MouseButtonType.LEFT] = MouseButtonType.LEFT
    num_clicks: int = 2


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
