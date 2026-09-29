from __future__ import annotations

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import Document
from app.ingestion.file_registry import (
    DOCUMENT_ROOT,
    sync_document_directory,
)
from app.ingestion.manager import get_ingestion_manager


class DocumentChangeHandler(FileSystemEventHandler):
    """Synchronize filesystem changes and enqueue background indexing."""

    def _sync(self) -> None:
        try:
            print("\n[WATCHER] Change detected.")
            sync_document_directory()

            manager = get_ingestion_manager()
            with SessionLocal() as db:
                ready_ids = db.execute(
                    select(Document.id).where(
                        Document.status == "READY_FOR_INGESTION"
                    )
                ).scalars().all()

                deleted_ids = db.execute(
                    select(Document.id).where(
                        Document.status == "DELETED"
                    )
                ).scalars().all()

            for document_id in ready_ids:
                manager.enqueue_index(document_id)

            for document_id in deleted_ids:
                manager.enqueue_delete(document_id)

        except Exception as exc:
            print(f"[WATCHER ERROR] {exc}")

    def on_created(self, event):
        if not event.is_directory:
            self._sync()

    def on_modified(self, event):
        if not event.is_directory:
            self._sync()

    def on_deleted(self, event):
        if not event.is_directory:
            self._sync()

    def on_moved(self, event):
        if not event.is_directory:
            self._sync()


def start_watcher() -> None:
    DOCUMENT_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    DocumentChangeHandler()._sync()

    observer = Observer()
    observer.schedule(
        DocumentChangeHandler(),
        str(DOCUMENT_ROOT),
        recursive=True,
    )
    observer.start()

    print(f"\nWatching:\n{DOCUMENT_ROOT}")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            input()
    except KeyboardInterrupt:
        print("\nStopping watcher...")
        observer.stop()

    observer.join()


if __name__ == "__main__":
    start_watcher()
