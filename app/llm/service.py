from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import User
from app.llm.client import (
    AsyncLLMClient,
    LLMResult,
    get_llm_client,
)
from app.llm.config import (
    LLMSettings,
    get_llm_settings,
)
from app.llm.prompts import (
    build_messages,
    sanitize_citations,
)
from app.retrieval.retriever import (
    SecureRetriever,
)
from app.retrieval.types import SearchResult


@dataclass(slots=True)
class Citation:
    source_id: str
    citation: str
    document_id: int | None


@dataclass(slots=True)
class RAGAnswer:
    answer: str
    citations: list[Citation]
    retrieved_results: list[SearchResult]
    model: str
    usage_prompt_tokens: int
    usage_completion_tokens: int
    usage_total_tokens: int
    llm_key_slot: int


class SecureRAGService:
    """
    End-to-end SecureRAG answer service.

    Pipeline:

        user
          ↓
        SecureRetriever
          ↓
        authorized chunks
          ↓
        bounded prompt context
          ↓
        Groq
          ↓
        grounded answer + citations
    """

    def __init__(
        self,
        retriever: SecureRetriever | None = None,
        llm_client: AsyncLLMClient | None = None,
        settings: LLMSettings | None = None,
    ) -> None:
        self.settings = (
            settings
            or get_llm_settings()
        )

        self.retriever = (
            retriever
            or SecureRetriever()
        )

        self.llm_client = (
            llm_client
            or get_llm_client()
        )

    async def answer(
        self,
        db: Session,
        user: User,
        query: str,
        *,
        top_k: int | None = None,
        candidate_k: int | None = None,
    ) -> RAGAnswer:

        query = query.strip()

        if not query:
            raise ValueError(
                "Query cannot be empty."
            )

        top_k = (
            top_k
            or self.settings.rag_top_k
        )

        candidate_k = (
            candidate_k
            or self.settings.rag_candidate_k
        )

        # ---------------------------------------------------------
        # 1. SECURE RETRIEVAL
        # ---------------------------------------------------------
        results = self.retriever.search(
            db=db,
            user=user,
            query=query,
            top_k=top_k,
            candidate_k=candidate_k,
            rrf_k=60,
        )

        # ---------------------------------------------------------
        # 2. No accessible evidence
        # ---------------------------------------------------------
        if not results:
            return RAGAnswer(
                answer=(
                    "I couldn't find enough information "
                    "in the documents you have access to."
                ),
                citations=[],
                retrieved_results=[],
                model=self.settings.groq_model,
                usage_prompt_tokens=0,
                usage_completion_tokens=0,
                usage_total_tokens=0,
                llm_key_slot=0,
            )

        # ---------------------------------------------------------
        # 3. Build grounded prompt
        # ---------------------------------------------------------
        messages, source_map = (
            build_messages(
                query=query,
                results=results,
                max_context_chars=(
                    self.settings.rag_max_context_chars
                ),
            )
        )

        # ---------------------------------------------------------
        # 4. Generate answer
        # ---------------------------------------------------------
        llm_result: LLMResult = (
            await self.llm_client.complete(
                messages=messages,
            )
        )

        answer = sanitize_citations(
            llm_result.text,
            source_map,
        )

        # ---------------------------------------------------------
        # 5. Build citation objects
        #
        # We expose the complete retrieved source set.
        # The answer itself contains inline [S#] references.
        # ---------------------------------------------------------
        citations = [
            Citation(
                source_id=source_id,
                citation=result.citation,
                document_id=result.document_id,
            )
            for source_id, result
            in source_map.items()
        ]

        return RAGAnswer(
            answer=answer,
            citations=citations,
            retrieved_results=results,
            model=llm_result.model,
            usage_prompt_tokens=(
                llm_result.usage.prompt_tokens
            ),
            usage_completion_tokens=(
                llm_result.usage.completion_tokens
            ),
            usage_total_tokens=(
                llm_result.usage.total_tokens
            ),
            llm_key_slot=llm_result.key_slot,
        )