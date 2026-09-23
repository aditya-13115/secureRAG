from __future__ import annotations

from pydantic import (
    BaseModel,
    Field,
)


class ChatRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=4000,
    )

    top_k: int = Field(
        default=8,
        ge=1,
        le=12,
    )


class CitationResponse(BaseModel):
    source_id: str
    citation: str
    document_id: int | None


class ChatResponse(BaseModel):
    answer: str
    citations: list[CitationResponse]

    retrieval_count: int

    model: str

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int