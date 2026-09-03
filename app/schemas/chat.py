from pydantic import BaseModel, Field
from typing_extensions import Literal

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ChatRole(BaseModel):
    role: Literal["user", "assistant"] = Field(
        ..., description="Must be 'user' or 'assistant'."
    )
    content: str = Field(..., description="The message text.")


class ChatRequest(BaseModel):
    message: str = Field(..., description="The user's new message.")
    history: list[ChatRole] = Field(
        default_factory=list,
        description="Optional prior conversation turns (user/assistant only).",
    )
    customer_id: int | None = Field(
        default=None, description="Optional customer id used when creating a bill."
    )


class ChatResponse(BaseModel):
    reply: str = Field(..., description="The assistant reply.")
    history: list[dict] = Field(...,
                                description="Updated history including the new exchange.")
    tool_calls_used: list[str] = Field(default_factory=list)
