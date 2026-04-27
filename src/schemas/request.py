from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from src.schemas.computer_action import ComputerAction


class _FrozenBaseModel(BaseModel):
    model_config = ConfigDict(
        frozen=True,
    )


class _BaseEnvRequest(_FrozenBaseModel):
    session_id: int
    task_id: str
    include_a11y: bool = False


class StartRequest(_BaseEnvRequest):
    op: Literal["start"]


class ActionRequest(_BaseEnvRequest):
    op: Literal["action"]
    actions: list[ComputerAction] = Field(min_length=1)


class RewardRequest(_BaseEnvRequest):
    op: Literal["reward"]


Request = Annotated[
    Union[StartRequest, ActionRequest, RewardRequest],
    Field(discriminator="op"),
]
