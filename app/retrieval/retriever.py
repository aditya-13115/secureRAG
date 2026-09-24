from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import (
    Session,
    selectinload,
)

from app.auth.acl import can_access
from app.db.models import Document, User
from app.retrieval.bm25 import (
    BM25Retriever,
)
from app.retrieval.embeddings import (
    get_embedding_model,
)
from app.retrieval.hybrid import (
    HybridRetriever,
)
from app.retrieval.semantic import (
    SemanticRetriever,
)
from app.retrieval.types import SearchResult
from app.retrieval.vector_store import (
    ChromaVectorStore,
)


class SecureRetriever:
    """
    Public retrieval API for SecureRAG.

    The caller does NOT select semantic/BM25/hybrid.

    Retrieval is always:

        User
          ↓
        ACL
          ↓
        allowed document IDs
          ↓
        Semantic 65%
        BM25     35%
          ↓
        Weighted RRF
          ↓
        final authorized chunks
    """

    def __init__(
        self,
        vector_store: ChromaVectorStore | None = None,
        bm25_store: BM25Retriever | None = None,
    ) -> None:

        vector_store = (
            vector_store
            or ChromaVectorStore()
        )

        bm25_store = (
            bm25_store
            or BM25Retriever()
        )

        embedding_model = (
            get_embedding_model()
        )

        semantic_retriever = (
            SemanticRetriever(
                vector_store=vector_store,
                embedding_model=embedding_model,
            )
        )

        self.hybrid_retriever = (
            HybridRetriever(
                semantic_retriever=semantic_retriever,
                bm25_retriever=bm25_store,
                semantic_weight=0.65,
                bm25_weight=0.35,
            )
        )

    @staticmethod
    def get_allowed_document_ids(
        db: Session,
        user: User,
    ) -> list[int]:
        """
        Resolve authorization from SQL.

        Only indexed documents can reach retrieval.

        The search indexes themselves are NOT
        the source of truth for permissions.
        """

        documents = db.execute(
            select(Document)
            .options(
                selectinload(
                    Document.allowed_roles
                ),
                selectinload(
                    Document.allowed_departments
                ),
                selectinload(
                    Document.allowed_users
                ),
            )
            .where(
                Document.status == "INDEXED"
            )
        ).scalars().unique().all()

        allowed_document_ids: list[int] = []

        for document in documents:
            if can_access(
                user,
                document,
            ):
                allowed_document_ids.append(
                    document.id
                )

        return allowed_document_ids

    def search(
        self,
        db: Session,
        user: User,
        query: str,
        *,
        top_k: int = 10,
        candidate_k: int = 30,
        rrf_k: int = 60,
        preferred_document_ids: list[int] | None = None,
    ) -> list[SearchResult]:
        """
        The only retrieval method the rest of the application needs.

        Hybrid retrieval is always used.
        """

        if not query or not query.strip():
            return []

        allowed_document_ids = (
            self.get_allowed_document_ids(
                db=db,
                user=user,
            )
        )

        if not allowed_document_ids:
            return []

        # Optional relevance narrowing for targeted queries.
        # Authorization is always applied first; preferred IDs can
        # never expand the user's access set.
        if preferred_document_ids:
            preferred = set(
                preferred_document_ids
            )
            allowed_document_ids = [
                document_id
                for document_id in allowed_document_ids
                if document_id in preferred
            ]

            if not allowed_document_ids:
                return []

        return self.hybrid_retriever.search(
            query=query,
            allowed_document_ids=allowed_document_ids,
            top_k=top_k,
            candidate_k=candidate_k,
            rrf_k=rrf_k,
        )