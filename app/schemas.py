from pydantic import BaseModel


class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]


class ChatResponse(BaseModel):
    message: str
    image_url: str | None = None


# --- CUA (Computer Use Agent) format ---

class CUATranscriptEntry(BaseModel):
    speaker: str
    timestamp: str
    content: str


class CUAQuery(BaseModel):
    timestamp: str
    content: str


class CUAActiveQuery(BaseModel):
    speaker: str  # the customer — maps to role: "user"
    queries: list[CUAQuery]


class CUAMetadata(BaseModel):
    platform: str | None = None
    context: str | None = None


class CUAChatRequest(BaseModel):
    conversation_transcript: list[CUATranscriptEntry]
    active_query: CUAActiveQuery
    metadata: CUAMetadata | None = None
