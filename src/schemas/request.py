from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter

from src.schemas.computer_action import ComputerAction


class BaseEnvRequest(BaseModel):
    session_id: int
    task_id: str
    include_a11y: bool = False


class StartRequest(BaseEnvRequest):
    op: Literal["start"]


class ActionRequest(BaseEnvRequest):
    op: Literal["action"]
    actions: list[ComputerAction] = Field(min_length=1)


class RewardRequest(BaseEnvRequest):
    op: Literal["reward"]


Request = Annotated[
    Union[StartRequest, ActionRequest, RewardRequest],
    Field(discriminator="op"),
]


def parse_request_base(payload: dict[str, Any]) -> Request:
    """Parse a raw protocol payload into the matching request model."""
    return TypeAdapter(Request).validate_python(payload)
