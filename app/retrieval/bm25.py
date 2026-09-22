from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from app.retrieval.types import SearchResult


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_BM25_DB_PATH = (
    PROJECT_ROOT
    / "data"
    / "bm25.sqlite3"
)


STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "being",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "may",
    "might",
    "of",
    "on",
    "or",
    "our",
    "please",
    "should",
    "that",
    "the",
    "their",
    "them",
    "there",
    "these",
    "they",
    "this",
    "to",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "will",
    "with",
    "would",
    "you",
    "your",
}


class BM25Retriever:
    """
    Internal lexical/BM25 retrieval component.

    Uses a separate SQLite database from the
    authorization database.
    """

    TABLE_NAME = "chunk_bm25"

    def __init__(
        self,
        db_path: str | Path | None = None,
    ) -> None:
        self.db_path = Path(
            db_path
            or DEFAULT_BM25_DB_PATH
        )

        self.db_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            self.db_path,
            timeout=30,
        )

        conn.row_factory = sqlite3.Row

        conn.execute(
            "PRAGMA journal_mode=WAL"
        )

        conn.execute(
            "PRAGMA busy_timeout=30000"
        )

        return conn

    def _ensure_table(self) -> None:
        with self._connect() as conn:
            conn.execute(
                f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS
                {self.TABLE_NAME}
                USING fts5(
                    chunk_id UNINDEXED,
                    document_id UNINDEXED,
                    text,
                    metadata_json UNINDEXED,
                    tokenize='unicode61'
                )
                """
            )

            conn.commit()

    @staticmethod
    def _tokenize(
        text: str,
    ) -> list[str]:
        tokens = re.findall(
            r"[\w]+",
            text.lower(),
            flags=re.UNICODE,
        )

        return [
            token
            for token in tokens
            if len(token) >= 2
            and token not in STOP_WORDS
        ]

    @classmethod
    def _build_match_query(
        cls,
        query: str,
        operator: str,
    ) -> str:
        tokens = cls._tokenize(
            query
        )

        if not tokens:
            return ""

        operator = operator.upper()

        if operator not in {
            "AND",
            "OR",
        }:
            raise ValueError(
                "operator must be AND or OR"
            )

        return f" {operator} ".join(
            f'"{token}"'
            for token in tokens
        )

    def delete_document(
        self,
        document_id: int,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                f"""
                DELETE FROM {self.TABLE_NAME}
                WHERE document_id = ?
                """,
                (document_id,),
            )

            conn.commit()

    def upsert_chunks(
        self,
        chunk_ids: list[str],
        texts: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        if not chunk_ids:
            return

        if not (
            len(chunk_ids)
            == len(texts)
            == len(metadatas)
        ):
            raise ValueError(
                "chunk_ids, texts and metadatas "
                "must have the same length."
            )

        rows = [
            (
                chunk_id,
                metadata["document_id"],
                text,
                json.dumps(
                    metadata,
                    ensure_ascii=False,
                ),
            )
            for chunk_id, text, metadata
            in zip(
                chunk_ids,
                texts,
                metadatas,
            )
        ]

        with self._connect() as conn:
            conn.executemany(
                f"""
                INSERT INTO {self.TABLE_NAME}
                (
                    chunk_id,
                    document_id,
                    text,
                    metadata_json
                )
                VALUES (?, ?, ?, ?)
                """,
                rows,
            )

            conn.commit()

    def replace_document(
        self,
        document_id: int,
        chunk_ids: list[str],
        texts: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        self.delete_document(
            document_id
        )

        self.upsert_chunks(
            chunk_ids=chunk_ids,
            texts=texts,
            metadatas=metadatas,
        )

    def _search_query(
        self,
        match_query: str,
        allowed_document_ids: list[int],
        top_k: int,
    ) -> list[SearchResult]:

        placeholders = ",".join(
            "?"
            for _ in allowed_document_ids
        )

        sql = f"""
            SELECT
                chunk_id,
                document_id,
                text,
                metadata_json,
                bm25({self.TABLE_NAME}) AS bm25_score
            FROM {self.TABLE_NAME}
            WHERE {self.TABLE_NAME} MATCH ?
              AND document_id IN ({placeholders})
            ORDER BY bm25_score ASC
            LIMIT ?
        """

        params = [
            match_query,
            *allowed_document_ids,
            top_k,
        ]

        with self._connect() as conn:
            rows = conn.execute(
                sql,
                params,
            ).fetchall()

        results: list[SearchResult] = []

        for rank, row in enumerate(
            rows,
            start=1,
        ):
            metadata = json.loads(
                row["metadata_json"]
            )

            # SQLite BM25 uses lower = better.
            # Convert to higher = better.
            score = -float(
                row["bm25_score"]
            )

            results.append(
                SearchResult(
                    chunk_id=row["chunk_id"],
                    text=row["text"],
                    score=score,
                    metadata=metadata,
                    rank=rank,
                    source="bm25",
                    sources=("bm25",),
                )
            )

        return results

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

        if top_k <= 0:
            return []

        # First prefer documents containing ALL
        # meaningful query terms.
        and_query = self._build_match_query(
            query,
            operator="AND",
        )

        if not and_query:
            return []

        results = self._search_query(
            match_query=and_query,
            allowed_document_ids=allowed_document_ids,
            top_k=top_k,
        )

        if results:
            return results

        # If AND is too restrictive, fall back to OR.
        or_query = self._build_match_query(
            query,
            operator="OR",
        )

        if not or_query:
            return []

        if or_query == and_query:
            return []

        return self._search_query(
            match_query=or_query,
            allowed_document_ids=allowed_document_ids,
            top_k=top_k,
        )