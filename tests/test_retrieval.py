from __future__ import annotations

import pytest
from sqlalchemy import select

from app.auth.acl import can_access
from app.db.database import SessionLocal
from app.db.models import Document, User
from app.retrieval.hybrid import (
    weighted_reciprocal_rank_fusion,
)
from app.retrieval.retriever import (
    SecureRetriever,
)
from app.retrieval.types import SearchResult


# ============================================================
# HELPERS
# ============================================================


def get_user(
    db,
    email: str,
) -> User:
    return db.execute(
        select(User).where(
            User.email == email
        )
    ).scalar_one()


# ============================================================
# FIXTURES
# ============================================================


@pytest.fixture(scope="module")
def retriever() -> SecureRetriever:
    """
    Load the embedding model only once for this test module.
    """
    return SecureRetriever()


@pytest.fixture
def db():
    session = SessionLocal()

    try:
        yield session
    finally:
        session.close()


# ============================================================
# RRF UNIT TESTS
# ============================================================


def test_weighted_rrf_combines_both_retrievers():
    """
    Verify that a result appearing in both semantic and BM25
    receives contributions from both retrieval systems.
    """

    semantic_a = SearchResult(
        chunk_id="chunk-a",
        text="A",
        score=0.91,
        metadata={
            "document_id": 1,
        },
        rank=1,
        source="semantic",
        sources=("semantic",),
    )

    semantic_b = SearchResult(
        chunk_id="chunk-b",
        text="B",
        score=0.88,
        metadata={
            "document_id": 2,
        },
        rank=2,
        source="semantic",
        sources=("semantic",),
    )

    bm25_a = SearchResult(
        chunk_id="chunk-a",
        text="A",
        score=8.2,
        metadata={
            "document_id": 1,
        },
        rank=1,
        source="bm25",
        sources=("bm25",),
    )

    bm25_c = SearchResult(
        chunk_id="chunk-c",
        text="C",
        score=6.2,
        metadata={
            "document_id": 3,
        },
        rank=2,
        source="bm25",
        sources=("bm25",),
    )

    results = weighted_reciprocal_rank_fusion(
        semantic_results=[
            semantic_a,
            semantic_b,
        ],
        bm25_results=[
            bm25_a,
            bm25_c,
        ],
        semantic_weight=0.65,
        bm25_weight=0.35,
        rrf_k=60,
        top_k=3,
    )

    assert len(results) == 3

    first = results[0]

    assert first.chunk_id == "chunk-a"

    assert set(first.sources) == {
        "semantic",
        "bm25",
    }

    assert (
        first.score
        > results[-1].score
    )


# ============================================================
# ACL DOCUMENT SET TESTS
# ============================================================


def test_engineer_has_expected_access(
    db,
    retriever,
):
    user = get_user(
        db,
        "engineer@monke.ai",
    )

    allowed_ids = (
        retriever.get_allowed_document_ids(
            db=db,
            user=user,
        )
    )

    assert len(allowed_ids) == 15


def test_employee_has_public_access_only(
    db,
    retriever,
):
    user = get_user(
        db,
        "employee@monke.ai",
    )

    allowed_ids = (
        retriever.get_allowed_document_ids(
            db=db,
            user=user,
        )
    )

    documents = db.execute(
        select(Document).where(
            Document.id.in_(allowed_ids)
        )
    ).scalars().all()

    assert len(documents) == 9

    assert all(
        document.access_scope == "PUBLIC"
        for document in documents
    )


def test_finance_head_access(
    db,
    retriever,
):
    user = get_user(
        db,
        "finance.head@monke.ai",
    )

    allowed_ids = (
        retriever.get_allowed_document_ids(
            db=db,
            user=user,
        )
    )

    assert len(allowed_ids) == 21


def test_ceo_can_access_all_indexed_documents(
    db,
    retriever,
):
    user = get_user(
        db,
        "ceo@monke.ai",
    )

    allowed_ids = (
        retriever.get_allowed_document_ids(
            db=db,
            user=user,
        )
    )

    indexed_count = db.execute(
        select(Document).where(
            Document.status == "INDEXED"
        )
    ).scalars().all()

    assert len(allowed_ids) == len(
        indexed_count
    )


# ============================================================
# HYBRID RETRIEVAL TESTS
# ============================================================


def test_hybrid_retrieval_returns_results(
    db,
    retriever,
):
    """
    Basic end-to-end retrieval test.
    """

    user = get_user(
        db,
        "engineer@monke.ai",
    )

    results = retriever.search(
        db=db,
        user=user,
        query="Q3 technology priorities",
        top_k=10,
        candidate_k=30,
        rrf_k=60,
    )

    assert results

    assert len(results) <= 10


def test_hybrid_results_are_ranked(
    db,
    retriever,
):
    user = get_user(
        db,
        "engineer@monke.ai",
    )

    results = retriever.search(
        db=db,
        user=user,
        query="Q3 technology priorities",
        top_k=10,
    )

    scores = [
        result.score
        for result in results
    ]

    assert scores == sorted(
        scores,
        reverse=True,
    )


def test_hybrid_results_have_source_metadata(
    db,
    retriever,
):
    user = get_user(
        db,
        "engineer@monke.ai",
    )

    results = retriever.search(
        db=db,
        user=user,
        query="Q3 technology priorities",
        top_k=10,
    )

    assert results

    for result in results:
        assert result.chunk_id
        assert result.text
        assert result.metadata
        assert result.citation


# ============================================================
# SECURITY / ACL LEAKAGE TESTS
# ============================================================


@pytest.mark.parametrize(
    "email,query",
    [
        (
            "engineer@monke.ai",
            "finance revenue budget forecast",
        ),
        (
            "employee@monke.ai",
            "finance compensation budget",
        ),
        (
            "marketing@monke.ai",
            "employee salary compensation benefits",
        ),
    ],
)
def test_hybrid_never_returns_unauthorized_documents(
    db,
    retriever,
    email: str,
    query: str,
):
    """
    Core SecureRAG security property:

    Unauthorized documents must never appear in the
    final retrieval results.
    """

    user = get_user(
        db,
        email,
    )

    allowed_ids = set(
        retriever.get_allowed_document_ids(
            db=db,
            user=user,
        )
    )

    results = retriever.search(
        db=db,
        user=user,
        query=query,
        top_k=10,
        candidate_k=30,
    )

    for result in results:
        assert (
            result.document_id
            in allowed_ids
        )


def test_engineer_cannot_access_finance_document(
    db,
):
    user = get_user(
        db,
        "engineer@monke.ai",
    )

    finance_document = db.execute(
        select(Document).where(
            Document.relative_path.like(
                "finance/%"
            )
        )
    ).scalars().first()

    assert finance_document is not None

    assert (
        can_access(
            user,
            finance_document,
        )
        is False
    )


def test_employee_can_only_access_public_documents(
    db,
):
    user = get_user(
        db,
        "employee@monke.ai",
    )

    documents = db.execute(
        select(Document).where(
            Document.status == "INDEXED"
        )
    ).scalars().all()

    accessible = [
        document
        for document in documents
        if can_access(
            user,
            document,
        )
    ]

    assert accessible

    assert all(
        document.access_scope == "PUBLIC"
        for document in accessible
    )


# ============================================================
# PUBLIC RETRIEVAL TEST
# ============================================================


def test_employee_can_retrieve_public_content(
    db,
    retriever,
):
    user = get_user(
        db,
        "employee@monke.ai",
    )

    results = retriever.search(
        db=db,
        user=user,
        query="company overview Monk-E",
        top_k=10,
    )

    assert results

    allowed_ids = set(
        retriever.get_allowed_document_ids(
            db=db,
            user=user,
        )
    )

    assert all(
        result.document_id in allowed_ids
        for result in results
    )


# ============================================================
# GLOBAL USER TEST
# ============================================================


def test_ceo_can_retrieve_finance_content(
    db,
    retriever,
):
    user = get_user(
        db,
        "ceo@monke.ai",
    )

    results = retriever.search(
        db=db,
        user=user,
        query="Q3 revenue budget forecast",
        top_k=10,
    )

    assert results

    allowed_ids = set(
        retriever.get_allowed_document_ids(
            db=db,
            user=user,
        )
    )

    assert all(
        result.document_id in allowed_ids
        for result in results
    )