from __future__ import annotations

from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from app.ingestion.file_registry import (
    DOCUMENT_ROOT,
    sync_document_directory,
)


class DocumentChangeHandler(
    FileSystemEventHandler
):
    """
    Reacts to document filesystem changes.

    For the prototype we simply re-run the directory
    synchronization. This is intentionally simple and
    reliable for a small document corpus.
    """

    def _sync(self) -> None:
        try:
            print("\n[WATCHER] Change detected.")
            sync_document_directory()

        except Exception as exc:
            print(
                f"[WATCHER ERROR] {exc}"
            )

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

    # Initial synchronization.
    sync_document_directory()

    event_handler = DocumentChangeHandler()

    observer = Observer()

    observer.schedule(
        event_handler,
        str(DOCUMENT_ROOT),
        recursive=True,
    )

    observer.start()

    print(
        f"\nWatching:\n{DOCUMENT_ROOT}"
    )

    print(
        "Press Ctrl+C to stop.\n"
    )

    try:
        while True:
            input()

    except KeyboardInterrupt:
        print("\nStopping watcher...")

        observer.stop()

    observer.join()


if __name__ == "__main__":
    start_watcher()