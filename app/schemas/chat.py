from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    type: Literal["message"] = "message"
    sender: str
    message: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class ChatStatus(BaseModel):
    type: Literal["status"] = "status"
    message: str
    user_count: int
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class RoomStatusResponse(BaseModel):
    room_id: str
    count: int
    max_users: int = 2
    is_full: bool
    active_users: list[str]
