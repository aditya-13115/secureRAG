from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth.acl import can_access
from app.db.models import Document, User
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
    ACCESS_HINT_AUTHORIZED,
    ACCESS_HINT_DENIED,
    ACCESS_HINT_NORMAL,
    build_messages,
    sanitize_citations,
)
from app.retrieval.retriever import SecureRetriever
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


SENSITIVE_TERMS = frozenset(
    {
        "salary",
        "salaries",
        "compensation",
        "compensations",
        "ctc",
        "payroll",
        "payslip",
        "payslips",
        "bonus",
        "bonuses",
        "benefits",
        "remuneration",
        "appraisal",
        "appraisals",
        "increment",
        "increments",
        "performance-review",
    }
)

SENSITIVE_DEPARTMENT_CODES = frozenset(
    {"HR", "FIN"}
)


def _query_tokens(query: str) -> set[str]:
    return {
        token
        for token in re.findall(
            r"[a-z0-9][a-z0-9_-]*",
            query.lower(),
        )
        if len(token) >= 3
    }


def _is_sensitive_query(query: str) -> bool:
    tokens = _query_tokens(query)
    return bool(tokens & SENSITIVE_TERMS)


def _resolve_access_hint(
    db: Session,
    user: User,
    query: str,
) -> tuple[str, list[int] | None]:
    """
    Resolve a small application-side hint for sensitive queries.

    This does NOT replace the ACL engine. It only helps distinguish:

        authorized sensitive query
        inaccessible sensitive query
        ordinary query

    The check uses document metadata and the existing ACL function. It never
    sends unauthorized document content to the model.
    """

    if not _is_sensitive_query(query):
        return ACCESS_HINT_NORMAL, None

    documents = (
        db.execute(
            select(Document)
            .options(
                selectinload(Document.allowed_roles),
                selectinload(Document.allowed_departments),
                selectinload(Document.allowed_users),
                selectinload(Document.owner_department),
            )
            .where(Document.status == "INDEXED")
        )
        .scalars()
        .unique()
        .all()
    )

    # Prefer documents whose title/path/filename directly matches query
    # terms. This fixes queries such as "current compensation framework"
    # where the important concept is present in the filename/title but not
    # necessarily repeated in every spreadsheet chunk.
    query_tokens = _query_tokens(query)
    metadata_matches = []

    for document in documents:
        searchable = " ".join(
            (
                document.title,
                document.filename,
                document.relative_path,
            )
        ).lower()

        if any(
            token in searchable
            for token in query_tokens & SENSITIVE_TERMS
        ):
            metadata_matches.append(document)

    # If metadata does not identify a specific sensitive document, fall back
    # to the HR/Finance knowledge domains for this prototype. This lets a
    # query such as "Nisha's salary" find an HR spreadsheet even if the file
    # is named "compensation_framework_and_bands.xlsx".
    candidates = metadata_matches

    if not candidates:
        candidates = [
            document
            for document in documents
            if (
                document.owner_department is not None
                and document.owner_department.code
                in SENSITIVE_DEPARTMENT_CODES
                and document.classification
                in {"CONFIDENTIAL", "RESTRICTED"}
            )
        ]

    if not candidates:
        return ACCESS_HINT_NORMAL, None

    authorized_candidates = [
        document
        for document in candidates
        if can_access(user, document)
    ]

    if not authorized_candidates:
        return ACCESS_HINT_DENIED, []

    return (
        ACCESS_HINT_AUTHORIZED,
        [document.id for document in authorized_candidates],
    )


def get_cited_sources(
    answer: str,
    source_map: dict[str, SearchResult],
) -> list[tuple[str, SearchResult]]:
    """Return only sources explicitly cited by the final answer."""

    cited_ids = re.findall(r"\[S(\d+)\]", answer)

    sources: list[tuple[str, SearchResult]] = []
    seen: set[str] = set()

    for number in cited_ids:
        source_id = f"S{number}"

        if source_id in seen:
            continue

        result = source_map.get(source_id)
        if result is None:
            continue

        sources.append((source_id, result))
        seen.add(source_id)

    return sources


class SecureRAGService:
    """End-to-end SecureRAG answer service."""

    def __init__(
        self,
        retriever: SecureRetriever | None = None,
        llm_client: AsyncLLMClient | None = None,
        settings: LLMSettings | None = None,
    ) -> None:
        self.settings = settings or get_llm_settings()
        self.retriever = retriever or SecureRetriever()
        self.llm_client = llm_client or get_llm_client()

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
            raise ValueError("Query cannot be empty.")

        top_k = top_k or self.settings.rag_top_k
        candidate_k = candidate_k or self.settings.rag_candidate_k

        access_hint, preferred_document_ids = _resolve_access_hint(
            db=db,
            user=user,
            query=query,
        )

        # Authorization decisions remain outside the LLM. This avoids making
        # the model guess whether "missing" means "not indexed" or "denied".
        if access_hint == ACCESS_HINT_DENIED:
            return RAGAnswer(
                answer="You don't have access to that information.",
                citations=[],
                retrieved_results=[],
                model=self.settings.groq_model,
                usage_prompt_tokens=0,
                usage_completion_tokens=0,
                usage_total_tokens=0,
                llm_key_slot=0,
            )

        results = self.retriever.search(
            db=db,
            user=user,
            query=query,
            top_k=top_k,
            candidate_k=candidate_k,
            rrf_k=60,
            preferred_document_ids=preferred_document_ids,
        )

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

        messages, source_map = build_messages(
            query=query,
            results=results,
            max_context_chars=self.settings.rag_max_context_chars,
            access_hint=access_hint,
        )

        llm_result: LLMResult = await self.llm_client.complete(
            messages=messages,
        )

        answer = sanitize_citations(
            llm_result.text,
            source_map,
        )

        cited_sources = get_cited_sources(
            answer,
            source_map,
        )

        citations = [
            Citation(
                source_id=source_id,
                citation=result.citation,
                document_id=result.document_id,
            )
            for source_id, result in cited_sources
        ]

        return RAGAnswer(
            answer=answer,
            citations=citations,
            retrieved_results=results,
            model=llm_result.model,
            usage_prompt_tokens=llm_result.usage.prompt_tokens,
            usage_completion_tokens=llm_result.usage.completion_tokens,
            usage_total_tokens=llm_result.usage.total_tokens,
            llm_key_slot=llm_result.key_slot,
        )
