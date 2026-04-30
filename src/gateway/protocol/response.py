from __future__ import annotations

from enum import Enum
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field


class _FrozenBaseModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ResponseStatus(str, Enum):
    OK = "ok"
    ERROR = "error"


class ImagePayload(_FrozenBaseModel):
    data: str = ""
    mime_type: str = Field(default="image/png", alias="mimeType")


class _BaseResponse(_FrozenBaseModel):
    session_id: int
    task_id: str


class ActionResponse(_BaseResponse):
    status: Literal[ResponseStatus.OK] = ResponseStatus.OK
    text: str | None = None
    image: ImagePayload


class RewardResponse(_BaseResponse):
    status: Literal[ResponseStatus.OK] = ResponseStatus.OK
    reward: float


class ErrorResponseType(str, Enum):
    GATEWAY_BUSY = "gateway_busy"
    FAIL_REQUEST_HANDLE = "fail_request_handle"
    NO_OPERATION_BUDGET = "no_operation_budget"


ERROR_MESSAGES: dict[ErrorResponseType, str] = {
    ErrorResponseType.GATEWAY_BUSY: "Timed out waiting for gateway in-flight capacity.",
    ErrorResponseType.FAIL_REQUEST_HANDLE: "WEBGYM-RL failed to handle request.",
    ErrorResponseType.NO_OPERATION_BUDGET: "No operation budget remains after gateway admission.",
}


class ErrorResponse(_BaseResponse):
    status: Literal[ResponseStatus.ERROR] = ResponseStatus.ERROR
    error_type: ErrorResponseType
    message: str

    @classmethod
    def from_type(
        cls,
        *,
        session_id: int,
        task_id: str,
        error_type: ErrorResponseType,
    ) -> "ErrorResponse":
        return cls(
            session_id=session_id,
            task_id=task_id,
            error_type=error_type,
            message=ERROR_MESSAGES[error_type],
        )


Response: TypeAlias = ActionResponse | RewardResponse | ErrorResponse
