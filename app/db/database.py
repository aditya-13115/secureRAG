from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "monke_second_brain.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "check_same_thread": False,
        "timeout": 30,
    },
    echo=False,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


DOCUMENT_MIGRATIONS = {
    "created_by_user_id": "INTEGER",
    "policy_updated_by_user_id": "INTEGER",
    "policy_updated_at": "DATETIME",
    "deleted_by_user_id": "INTEGER",
    "deleted_at": "DATETIME",
}


def _migrate_existing_documents() -> None:
    """Add new optional document audit columns to older prototype DBs."""
    inspector = inspect(engine)

    if "documents" not in inspector.get_table_names():
        return

    existing = {
        column["name"]
        for column in inspector.get_columns("documents")
    }

    missing = {
        name: ddl
        for name, ddl in DOCUMENT_MIGRATIONS.items()
        if name not in existing
    }

    with engine.begin() as connection:
        for name, ddl in missing.items():
            connection.exec_driver_sql(
                f"ALTER TABLE documents ADD COLUMN {name} {ddl}"
            )

        for column in (
            "created_by_user_id",
            "policy_updated_by_user_id",
            "deleted_by_user_id",
        ):
            connection.exec_driver_sql(
                f"CREATE INDEX IF NOT EXISTS ix_documents_{column} "
                f"ON documents ({column})"
            )


def init_db() -> None:
    """Create new tables and safely migrate the existing prototype DB."""
    Base.metadata.create_all(bind=engine)
    _migrate_existing_documents()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for obtaining a database session."""
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
