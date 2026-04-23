from __future__ import annotations

from enum import Enum
from typing import Optional, TypeAlias

from pydantic import BaseModel, Field


class ResponseStatus(str, Enum):
    OK = "ok"
    ERROR = "error"


class ImagePayload(BaseModel):
    data: str = ""
    mime_type: str = Field(default="image/png", alias="mimeType")


class _BaseResponse(BaseModel):
    session_id: int
    task_id: str
    status: ResponseStatus = ResponseStatus.OK


class ActionResponse(_BaseResponse):
    text: Optional[str] = None
    image: ImagePayload


class RewardResponse(_BaseResponse):
    reward: float


class ErrorResponse(_BaseResponse):
    status: ResponseStatus = ResponseStatus.ERROR
    error_type: ErrorType
    message: str


class ErrorType(str, Enum):
    GATEWAY_BUSY = "gateway_busy"


Response: TypeAlias = ActionResponse | RewardResponse | ErrorResponse
