from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from src.schemas.computer_action import ComputerAction


class _BaseEnvRequest(BaseModel):
    model_config = ConfigDict(
        frozen=True,
    )

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

RequestAdapter = TypeAdapter(Request)
