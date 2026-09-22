from __future__ import annotations

from collections import defaultdict

from app.retrieval.types import SearchResult


DEFAULT_SEMANTIC_WEIGHT = 0.65
DEFAULT_BM25_WEIGHT = 0.35
DEFAULT_RRF_K = 60


def weighted_reciprocal_rank_fusion(
    semantic_results: list[SearchResult],
    bm25_results: list[SearchResult],
    *,
    semantic_weight: float = DEFAULT_SEMANTIC_WEIGHT,
    bm25_weight: float = DEFAULT_BM25_WEIGHT,
    rrf_k: int = DEFAULT_RRF_K,
    top_k: int = 10,
) -> list[SearchResult]:
    """
    Weighted Reciprocal Rank Fusion.

    Semantic:
        weight = 0.65

    BM25:
        weight = 0.35

    Score:

        semantic_weight / (rrf_k + semantic_rank)
        +
        bm25_weight / (rrf_k + bm25_rank)

    This is rank-based, so raw semantic/BM25 scores
    do not need to be compared directly.
    """

    if semantic_weight < 0:
        raise ValueError(
            "semantic_weight cannot be negative."
        )

    if bm25_weight < 0:
        raise ValueError(
            "bm25_weight cannot be negative."
        )

    total_weight = (
        semantic_weight
        + bm25_weight
    )

    if total_weight <= 0:
        raise ValueError(
            "At least one retrieval weight must be positive."
        )

    if rrf_k <= 0:
        raise ValueError(
            "rrf_k must be greater than zero."
        )

    if top_k <= 0:
        return []

    # Normalize in case someone passes 65/35
    # instead of 0.65/0.35.
    semantic_weight /= total_weight
    bm25_weight /= total_weight

    fusion_scores: dict[
        str,
        float,
    ] = defaultdict(float)

    result_by_chunk: dict[
        str,
        SearchResult,
    ] = {}

    sources_by_chunk: dict[
        str,
        set[str],
    ] = defaultdict(set)

    # ---------------------------------------------------------
    # Semantic contribution
    # ---------------------------------------------------------
    for rank, result in enumerate(
        semantic_results,
        start=1,
    ):
        chunk_id = result.chunk_id

        fusion_scores[chunk_id] += (
            semantic_weight
            / (rrf_k + rank)
        )

        sources_by_chunk[chunk_id].add(
            "semantic"
        )

        result_by_chunk.setdefault(
            chunk_id,
            result,
        )

    # ---------------------------------------------------------
    # BM25 contribution
    # ---------------------------------------------------------
    for rank, result in enumerate(
        bm25_results,
        start=1,
    ):
        chunk_id = result.chunk_id

        fusion_scores[chunk_id] += (
            bm25_weight
            / (rrf_k + rank)
        )

        sources_by_chunk[chunk_id].add(
            "bm25"
        )

        result_by_chunk.setdefault(
            chunk_id,
            result,
        )

    # ---------------------------------------------------------
    # Final ranking
    # ---------------------------------------------------------
    ranked = sorted(
        fusion_scores.items(),
        key=lambda item: (
            -item[1],
            item[0],
        ),
    )

    final_results: list[SearchResult] = []

    for final_rank, (
        chunk_id,
        fusion_score,
    ) in enumerate(
        ranked[:top_k],
        start=1,
    ):
        original = result_by_chunk[
            chunk_id
        ]

        final_results.append(
            SearchResult(
                chunk_id=chunk_id,
                text=original.text,
                score=fusion_score,
                metadata=original.metadata,
                rank=final_rank,
                source="hybrid",
                sources=tuple(
                    sorted(
                        sources_by_chunk[
                            chunk_id
                        ]
                    )
                ),
            )
        )

    return final_results


class HybridRetriever:
    """
    Internal hybrid retrieval layer.

    Semantic + BM25 are always executed.
    Their rankings are combined with weighted RRF.

    No caller needs to select a retrieval technique.
    """

    def __init__(
        self,
        semantic_retriever,
        bm25_retriever,
        *,
        semantic_weight: float = DEFAULT_SEMANTIC_WEIGHT,
        bm25_weight: float = DEFAULT_BM25_WEIGHT,
    ) -> None:
        self.semantic_retriever = (
            semantic_retriever
        )

        self.bm25_retriever = (
            bm25_retriever
        )

        self.semantic_weight = (
            semantic_weight
        )

        self.bm25_weight = (
            bm25_weight
        )

    def search(
        self,
        query: str,
        allowed_document_ids: list[int],
        *,
        top_k: int = 10,
        candidate_k: int = 30,
        rrf_k: int = DEFAULT_RRF_K,
    ) -> list[SearchResult]:

        if not query.strip():
            return []

        if not allowed_document_ids:
            return []

        semantic_results = (
            self.semantic_retriever.search(
                query=query,
                allowed_document_ids=allowed_document_ids,
                top_k=candidate_k,
            )
        )

        bm25_results = (
            self.bm25_retriever.search(
                query=query,
                allowed_document_ids=allowed_document_ids,
                top_k=candidate_k,
            )
        )

        return weighted_reciprocal_rank_fusion(
            semantic_results=semantic_results,
            bm25_results=bm25_results,
            semantic_weight=self.semantic_weight,
            bm25_weight=self.bm25_weight,
            rrf_k=rrf_k,
            top_k=top_k,
        )