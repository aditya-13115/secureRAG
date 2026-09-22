from __future__ import annotations

import os
from functools import lru_cache

from sentence_transformers import SentenceTransformer


DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class EmbeddingModel:
    """
    SentenceTransformer wrapper.

    The exact same model must be used for:
        - document indexing
        - query embedding
    """

    def __init__(
        self,
        model_name: str | None = None,
        device: str | None = None,
    ) -> None:
        self.model_name = model_name or os.getenv(
            "EMBEDDING_MODEL",
            DEFAULT_MODEL,
        )

        self.device = device or os.getenv(
            "EMBEDDING_DEVICE",
        )

        model_kwargs: dict[str, str] = {}

        if self.device:
            model_kwargs["device"] = self.device

        self.model = SentenceTransformer(
            self.model_name,
            **model_kwargs,
        )

    @property
    def dimension(self) -> int:
        dimension = (
            self.model.get_sentence_embedding_dimension()
        )

        if dimension is None:
            raise RuntimeError(
                "Embedding model did not expose an embedding dimension."
            )

        return int(dimension)

    def embed_documents(
        self,
        texts: list[str],
        batch_size: int = 32,
    ) -> list[list[float]]:
        if not texts:
            return []

        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        return embeddings.tolist()

    def embed_query(
        self,
        text: str,
    ) -> list[float]:
        if not text or not text.strip():
            raise ValueError(
                "Query text cannot be empty."
            )

        embedding = self.model.encode(
            [text],
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )[0]

        return embedding.tolist()


@lru_cache(maxsize=1)
def get_embedding_model() -> EmbeddingModel:
    """
    Singleton-style cache so the embedding model is
    loaded only once per Python process.
    """

    return EmbeddingModel()