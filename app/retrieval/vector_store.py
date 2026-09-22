from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import chromadb

from app.retrieval.types import SearchResult


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CHROMA_PATH = (
    PROJECT_ROOT / "data" / "chroma"
)

DEFAULT_COLLECTION_NAME = (
    "secure_rag_chunks"
)


class ChromaVectorStore:
    """
    Chroma vector index.

    Chroma is only a retrieval index.

    SQL remains the source of truth for:
        - users
        - documents
        - ACL
        - authorization
    """

    def __init__(
        self,
        persist_path: str | Path | None = None,
        collection_name: str | None = None,
    ) -> None:
        self.persist_path = Path(
            persist_path
            or os.getenv(
                "CHROMA_PATH",
                str(DEFAULT_CHROMA_PATH),
            )
        )

        self.collection_name = (
            collection_name
            or os.getenv(
                "CHROMA_COLLECTION",
                DEFAULT_COLLECTION_NAME,
            )
        )

        self.persist_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.client = chromadb.PersistentClient(
            path=str(self.persist_path)
        )

        self.collection = (
            self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={
                    "hnsw:space": "cosine",
                },
            )
        )

    def count(self) -> int:
        return self.collection.count()

    def delete_document(
        self,
        document_id: int,
    ) -> None:
        """
        Delete all chunks belonging to one document.
        """

        self.collection.delete(
            where={
                "document_id": document_id,
            }
        )

    def upsert_chunks(
        self,
        chunk_ids: list[str],
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        if not chunk_ids:
            return

        if not (
            len(chunk_ids)
            == len(texts)
            == len(embeddings)
            == len(metadatas)
        ):
            raise ValueError(
                "chunk_ids, texts, embeddings and "
                "metadatas must have the same length."
            )

        self.collection.upsert(
            ids=chunk_ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def replace_document(
        self,
        document_id: int,
        chunk_ids: list[str],
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """
        Replace all indexed chunks for a document.
        """

        self.delete_document(
            document_id
        )

        self.upsert_chunks(
            chunk_ids=chunk_ids,
            texts=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def search(
        self,
        query_embedding: list[float],
        allowed_document_ids: list[int],
        top_k: int = 30,
    ) -> list[SearchResult]:
        """
        Semantic search restricted to authorized documents.
        """

        if not allowed_document_ids:
            return []

        if top_k <= 0:
            return []

        result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where={
                "document_id": {
                    "$in": allowed_document_ids,
                }
            },
            include=[
                "documents",
                "metadatas",
                "distances",
            ],
        )

        ids = result.get(
            "ids",
            [[]],
        )[0]

        documents = result.get(
            "documents",
            [[]],
        )[0]

        metadatas = result.get(
            "metadatas",
            [[]],
        )[0]

        distances = result.get(
            "distances",
            [[]],
        )[0]

        results: list[SearchResult] = []

        for index, chunk_id in enumerate(ids):
            metadata = (
                metadatas[index]
                or {}
            )

            text = (
                documents[index]
                or ""
            )

            distance = float(
                distances[index]
            )

            # Chroma is configured with cosine distance.
            # Convert distance -> similarity.
            score = 1.0 - distance

            results.append(
                SearchResult(
                    chunk_id=chunk_id,
                    text=text,
                    score=score,
                    metadata=metadata,
                    rank=index + 1,
                    source="semantic",
                    sources=("semantic",),
                )
            )

        return results