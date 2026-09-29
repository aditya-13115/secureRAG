from __future__ import annotations

from dataclasses import dataclass
from queue import Empty, Queue
from threading import Event, Lock, Thread
from time import time

from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import Document


@dataclass(frozen=True, slots=True)
class IngestionJob:
    action: str
    document_id: int


class IngestionManager:
    """
    Small in-process background worker for indexing and index cleanup.

    The worker deliberately runs outside FastAPI's request/event-loop path,
    so uploads, policy changes, deletes and chat requests return without
    waiting for embedding/chunking work.
    """

    def __init__(self) -> None:
        self._queue: Queue[IngestionJob] = Queue()
        self._pending: set[tuple[str, int]] = set()
        self._lock = Lock()
        self._stop = Event()
        self._thread: Thread | None = None
        self._active: IngestionJob | None = None
        self._last_error: str | None = None
        self._last_finished_at: float | None = None

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return

            self._stop.clear()
            self._thread = Thread(
                target=self._run,
                name="securerag-ingestion-worker",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._queue.put(
            IngestionJob("__STOP__", -1)
        )

        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=5)

    def enqueue_index(self, document_id: int) -> bool:
        return self._enqueue(
            IngestionJob("INDEX", document_id)
        )

    def enqueue_delete(self, document_id: int) -> bool:
        return self._enqueue(
            IngestionJob("DELETE", document_id)
        )

    def _enqueue(self, job: IngestionJob) -> bool:
        key = (job.action, job.document_id)

        with self._lock:
            if key in self._pending:
                return False

            self._pending.add(key)
            self._queue.put(job)
            return True

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            active = self._active
            return {
                "running": bool(
                    self._thread
                    and self._thread.is_alive()
                ),
                "queue_depth": self._queue.qsize(),
                "active_job": (
                    {
                        "action": active.action,
                        "document_id": active.document_id,
                    }
                    if active
                    else None
                ),
                "last_error": self._last_error,
                "last_finished_at": self._last_finished_at,
            }

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                job = self._queue.get(timeout=0.5)
            except Empty:
                continue

            if job.action == "__STOP__":
                self._queue.task_done()
                break

            with self._lock:
                self._active = job

            try:
                if job.action == "INDEX":
                    self._process_index(job.document_id)
                elif job.action == "DELETE":
                    self._process_delete(job.document_id)
            except Exception as exc:  # pragma: no cover - defensive worker guard
                with self._lock:
                    self._last_error = (
                        f"{job.action} document {job.document_id}: {exc}"
                    )
                print(
                    "[INGESTION WORKER ERROR] "
                    f"{job.action} document={job.document_id}: {exc}"
                )
            finally:
                should_requeue_index = False

                with self._lock:
                    self._active = None
                    self._pending.discard(
                        (job.action, job.document_id)
                    )
                    self._last_finished_at = time()

                # If an index job became stale because a concurrent policy or
                # file change moved the document back to READY_FOR_INGESTION,
                # enqueue the current version now that the old job is no
                # longer marked pending. This avoids a lost update race.
                if job.action == "INDEX":
                    try:
                        with SessionLocal() as follow_up_db:
                            current = follow_up_db.execute(
                                select(Document).where(
                                    Document.id == job.document_id
                                )
                            ).scalar_one_or_none()
                            should_requeue_index = (
                                current is not None
                                and current.status == "READY_FOR_INGESTION"
                            )
                    except Exception as exc:  # pragma: no cover - defensive
                        with self._lock:
                            self._last_error = (
                                "INDEX follow-up check "
                                f"document {job.document_id}: {exc}"
                            )

                self._queue.task_done()

                if should_requeue_index:
                    self.enqueue_index(job.document_id)

    def _process_index(self, document_id: int) -> None:
        with SessionLocal() as db:
            document = db.execute(
                select(Document).where(
                    Document.id == document_id
                )
            ).scalar_one_or_none()

            if document is None:
                return

            if document.status != "READY_FOR_INGESTION":
                return

            print(
                f"[INGESTION] Starting document={document_id} "
                f"path={document.relative_path}"
            )

            # Heavy retrieval/embedding modules are imported only inside the
            # worker thread so FastAPI startup and normal chat requests do not
            # pay the model import/load cost.
            from app.retrieval.bm25 import BM25Retriever
            from app.retrieval.embeddings import get_embedding_model
            from app.retrieval.indexer import (
                IndexingSkipped,
                index_document,
            )
            from app.retrieval.vector_store import ChromaVectorStore

            embedding_model = get_embedding_model()
            vector_store = ChromaVectorStore()
            bm25_store = BM25Retriever()

            try:
                index_document(
                    db=db,
                    document=document,
                    embedding_model=embedding_model,
                    vector_store=vector_store,
                    bm25_store=bm25_store,
                )
            except IndexingSkipped as exc:
                # A policy/file/version change happened while this job was
                # running. The indexer cleaned the stale search data; a
                # follow-up job is scheduled after this job leaves the queue.
                print(
                    f"[INGESTION] Skipped stale index "
                    f"document={document_id}: {exc}"
                )
                return

            print(
                f"[INGESTION] Indexed document={document_id} "
                f"path={document.relative_path}"
            )

    def _process_delete(self, document_id: int) -> None:
        # Read-only search indexes are cleaned outside the SQL ACL path.
        # SQL status=DELETED already prevents new retrievals immediately.
        from app.retrieval.bm25 import BM25Retriever
        from app.retrieval.vector_store import ChromaVectorStore

        vector_store = ChromaVectorStore()
        bm25_store = BM25Retriever()

        vector_store.delete_document(document_id)
        bm25_store.delete_document(document_id)

        print(
            f"[INGESTION] Cleaned indexes for deleted document={document_id}"
        )


_MANAGER = IngestionManager()


def get_ingestion_manager(*, start: bool = True) -> IngestionManager:
    if start:
        _MANAGER.start()
    return _MANAGER
