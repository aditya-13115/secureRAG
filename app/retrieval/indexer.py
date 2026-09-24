from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from sqlalchemy import select
from sqlalchemy.orm import Session
from tqdm import tqdm

from app.db.database import (
    SessionLocal,
    init_db,
)
from app.db.models import Document
from app.ingestion.chunking import (
    chunk_document,
)
from app.ingestion.loaders import (
    load_document,
)
from app.retrieval.bm25 import (
    BM25Retriever,
)
from app.retrieval.embeddings import (
    EmbeddingModel,
    get_embedding_model,
)
from app.retrieval.vector_store import (
    ChromaVectorStore,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DOCUMENT_ROOT = (
    PROJECT_ROOT / "data" / "documents"
)


def get_document_path(
    document: Document,
) -> Path:
    """
    Resolve document.relative_path safely.

    Prevents paths outside data/documents.
    """

    base = (
        DOCUMENT_ROOT.resolve()
    )

    path = (
        base
        / Path(document.relative_path)
    ).resolve()

    if base not in path.parents:
        raise ValueError(
            "Document path escapes "
            f"document root: {document.relative_path}"
        )

    return path


def index_document(
    db: Session,
    document: Document,
    embedding_model: EmbeddingModel,
    vector_store: ChromaVectorStore,
    bm25_store: BM25Retriever,
) -> tuple[int, float]:

    started = perf_counter()

    document.status = "INDEXING"
    db.flush()

    try:
        path = get_document_path(
            document
        )

        if not path.exists():
            raise FileNotFoundError(
                f"Document does not exist: {path}"
            )

        # ----------------------------------
        # Load
        # ----------------------------------
        blocks = load_document(
            path
        )

        # ----------------------------------
        # Chunk
        # ----------------------------------
        chunks = chunk_document(
            document=document,
            blocks=blocks,
        )

        if not chunks:
            raise ValueError(
                f"No chunks generated for "
                f"document {document.id}"
            )

        chunk_ids = [
            chunk.chunk_id
            for chunk in chunks
        ]

        texts = [
            chunk.text
            for chunk in chunks
        ]

        metadatas = [
            chunk.chroma_metadata
            for chunk in chunks
        ]

        # Include document identity in the embedding input.
        # The stored/retrieved text remains the original chunk,
        # but queries such as "compensation framework" can now
        # semantically match a document whose filename/title carries
        # that concept even when the exact word is not repeated in
        # every spreadsheet chunk.
        embedding_inputs = [
            (
                f"Document title: {document.title}\n"
                f"Filename: {document.filename}\n"
                f"Content:\n{text}"
            )
            for text in texts
        ]

        # ----------------------------------
        # Embeddings
        # ----------------------------------
        embeddings = (
            embedding_model.embed_documents(
                embedding_inputs
            )
        )

        # ----------------------------------
        # Semantic index
        # ----------------------------------
        vector_store.replace_document(
            document_id=document.id,
            chunk_ids=chunk_ids,
            texts=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        # ----------------------------------
        # BM25 index
        # ----------------------------------
        bm25_store.replace_document(
            document_id=document.id,
            chunk_ids=chunk_ids,
            texts=texts,
            metadatas=metadatas,
        )

        document.status = "INDEXED"
        document.indexed_at = (
            datetime.now(timezone.utc)
        )

        db.commit()

        elapsed = (
            perf_counter() - started
        )

        return len(chunks), elapsed

    except Exception:
        db.rollback()

        # Clean any partially written indexes.
        try:
            vector_store.delete_document(
                document.id
            )
        except Exception:
            pass

        try:
            bm25_store.delete_document(
                document.id
            )
        except Exception:
            pass

        document.status = "FAILED"

        db.commit()

        raise


def index_ready_documents(
    db: Session,
    embedding_model: EmbeddingModel | None = None,
    vector_store: ChromaVectorStore | None = None,
    bm25_store: BM25Retriever | None = None,
) -> int:

    embedding_model = (
        embedding_model
        or get_embedding_model()
    )

    vector_store = (
        vector_store
        or ChromaVectorStore()
    )

    bm25_store = (
        bm25_store
        or BM25Retriever()
    )

    documents = db.execute(
        select(Document).where(
            Document.status
            == "READY_FOR_INGESTION"
        )
    ).scalars().all()

    total_documents = len(
        documents
    )

    if total_documents == 0:
        print(
            "\nNo documents ready "
            "for ingestion."
        )
        return 0

    print(
        "\n"
        + "=" * 70
    )
    print("SECURERAG INDEXING")
    print("=" * 70)
    print(
        f"Documents : {total_documents}"
    )
    print(
        f"Embedding : "
        f"{embedding_model.model_name}"
    )
    print(
        f"Chroma    : "
        f"{vector_store.persist_path}"
    )
    print(
        f"BM25 DB   : "
        f"{bm25_store.db_path}"
    )
    print("=" * 70)
    print()

    overall_start = perf_counter()

    indexed_count = 0
    failed_count = 0
    total_chunks = 0

    progress = tqdm(
        documents,
        desc="Indexing documents",
        unit="doc",
        dynamic_ncols=True,
    )

    for document in progress:
        try:
            chunk_count, elapsed = (
                index_document(
                    db=db,
                    document=document,
                    embedding_model=embedding_model,
                    vector_store=vector_store,
                    bm25_store=bm25_store,
                )
            )

            indexed_count += 1
            total_chunks += chunk_count

            progress.set_postfix(
                chunks=chunk_count,
                time=f"{elapsed:.2f}s",
            )

        except Exception as exc:
            failed_count += 1

            progress.set_postfix(
                status="FAILED"
            )

            tqdm.write(
                f"[FAILED] "
                f"{document.filename}: "
                f"{exc}"
            )

    total_elapsed = (
        perf_counter()
        - overall_start
    )

    average_time = (
        total_elapsed
        / indexed_count
        if indexed_count
        else 0.0
    )

    throughput = (
        indexed_count
        / total_elapsed
        if total_elapsed > 0
        else 0.0
    )

    print()
    print(
        "=" * 70
    )
    print("INDEXING COMPLETE")
    print("=" * 70)
    print(
        f"Indexed documents : "
        f"{indexed_count}"
    )
    print(
        f"Failed documents  : "
        f"{failed_count}"
    )
    print(
        f"Total chunks      : "
        f"{total_chunks}"
    )
    print(
        f"Total time        : "
        f"{total_elapsed:.2f}s"
    )
    print(
        f"Average/doc       : "
        f"{average_time:.2f}s"
    )
    print(
        f"Throughput        : "
        f"{throughput:.2f} docs/sec"
    )
    print(
        f"Chroma chunks     : "
        f"{vector_store.count()}"
    )
    print("=" * 70)

    return indexed_count


def main() -> None:
    init_db()

    db = SessionLocal()

    try:
        index_ready_documents(
            db
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()