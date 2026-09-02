from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ChatMessageResponse(BaseModel):
    response: str
    message_id: int


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    content: str
    created_at: datetime
