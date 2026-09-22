from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class SearchResult:
    """
    Normalized result returned by retrieval strategies.

    `score` has different meanings depending on the stage:
        - semantic: cosine similarity
        - bm25: transformed BM25 score
        - hybrid: weighted RRF score
    """

    chunk_id: str
    text: str
    score: float
    metadata: dict[str, Any]

    rank: int = 0
    source: str = ""
    sources: tuple[str, ...] = field(default_factory=tuple)

    @property
    def document_id(self) -> int | None:
        value = self.metadata.get("document_id")

        if value is None:
            return None

        return int(value)

    @property
    def citation(self) -> str:
        return str(
            self.metadata.get(
                "citation",
                "Unknown source",
            )
        )