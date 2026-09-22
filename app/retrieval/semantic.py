from __future__ import annotations

from app.retrieval.embeddings import (
    EmbeddingModel,
    get_embedding_model,
)
from app.retrieval.types import SearchResult
from app.retrieval.vector_store import (
    ChromaVectorStore,
)


class SemanticRetriever:
    """
    Internal semantic retrieval component.

    Not intended to be selected directly by the chat layer.
    """

    def __init__(
        self,
        vector_store: ChromaVectorStore | None = None,
        embedding_model: EmbeddingModel | None = None,
    ) -> None:
        self.vector_store = (
            vector_store
            or ChromaVectorStore()
        )

        self.embedding_model = (
            embedding_model
            or get_embedding_model()
        )

    def search(
        self,
        query: str,
        allowed_document_ids: list[int],
        top_k: int = 30,
    ) -> list[SearchResult]:

        if not query.strip():
            return []

        if not allowed_document_ids:
            return []

        query_embedding = (
            self.embedding_model.embed_query(
                query
            )
        )

        return self.vector_store.search(
            query_embedding=query_embedding,
            allowed_document_ids=allowed_document_ids,
            top_k=top_k,
        )