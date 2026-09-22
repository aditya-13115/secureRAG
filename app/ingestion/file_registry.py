from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import (
    Department,
    Document,
    Role,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DOCUMENT_ROOT = (
    PROJECT_ROOT / "data" / "documents"
).resolve()


SUPPORTED_EXTENSIONS = {
    ".pdf": "PDF",
    ".docx": "DOCX",
    ".xlsx": "XLSX",
    ".csv": "CSV",
    ".txt": "TXT",
    ".md": "MARKDOWN",
}


FOLDER_TO_DEPARTMENT = {
    "finance": "FIN",
    "hr": "HR",
    "technology": "TECH",
    "management": "MGT",
    "marketing": "MKT",
    "public": "GENERAL",
}


GLOBAL_ROLE_CODES = {
    "CEO",
    "CTO",
    "COFOUNDER",
}


RESTRICTED_ROLE_CODES = {
    "CEO",
    "CTO",
    "COFOUNDER",
    "FINANCE_HEAD",
    "HR_HEAD",
}


def utc_now():
    return datetime.now(timezone.utc)


def calculate_sha256(path: Path) -> str:
    """
    Calculate file checksum so we can detect content changes.
    """
    digest = hashlib.sha256()

    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)

    return digest.hexdigest()


def get_source_type(path: Path) -> str:
    return SUPPORTED_EXTENSIONS.get(
        path.suffix.lower(),
        "UNKNOWN",
    )


def build_document_key(relative_path: str) -> str:
    """
    Create a stable application-level key from the path.
    """
    digest = hashlib.sha256(
        relative_path.encode("utf-8")
    ).hexdigest()

    return f"DOC-{digest[:20]}"


def get_title(path: Path) -> str:
    """
    Convert:

        Q2_financial_review.pdf

    into:

        Q2 Financial Review
    """
    return (
        path.stem
        .replace("_", " ")
        .replace("-", " ")
        .strip()
    )


def infer_policy(
    category: str,
    filename: str,
) -> tuple[str, str]:
    """
    Prototype policy inference.

    In production this should come from an explicit admin
    policy rather than guessing from filenames.
    """

    filename_lower = filename.lower()

    # Public folder
    if category == "public":
        return "PUBLIC", "PUBLIC_INTERNAL"

    # Sensitive HR / Finance content
    sensitive_keywords = (
        "salary",
        "compensation",
        "payroll",
        "board_finance",
    )

    if any(
        keyword in filename_lower
        for keyword in sensitive_keywords
    ):
        return "ROLE", "RESTRICTED"

    # Department documents
    if category in {
        "finance",
        "hr",
    }:
        return "DEPARTMENT", "CONFIDENTIAL"

    return "DEPARTMENT", "INTERNAL"


def clear_document_acl(document: Document) -> None:
    """
    Remove previously inferred ACLs before rebuilding them.
    """

    document.allowed_departments.clear()
    document.allowed_roles.clear()
    document.allowed_users.clear()


def apply_document_acl(
    session,
    document: Document,
    category: str,
) -> None:
    """
    Build the prototype ACL from the document's location/policy.
    """

    clear_document_acl(document)

    access_scope, classification = infer_policy(
        category,
        document.filename,
    )

    document.access_scope = access_scope
    document.classification = classification

    if access_scope == "PUBLIC":
        return

    if access_scope == "ROLE":
        roles = (
            session.execute(
                select(Role).where(
                    Role.code.in_(RESTRICTED_ROLE_CODES)
                )
            )
            .scalars()
            .all()
        )

        document.allowed_roles.extend(roles)
        return

    if access_scope == "DEPARTMENT":
        department_code = FOLDER_TO_DEPARTMENT.get(
            category,
            "GENERAL",
        )

        department = (
            session.execute(
                select(Department).where(
                    Department.code == department_code
                )
            )
            .scalar_one()
        )

        document.allowed_departments.append(
            department
        )


def register_file(
    session,
    path: Path,
) -> Document | None:
    """
    Register one file in SQL.

    Behaviour:
    - New file       -> INSERT
    - Same checksum  -> UPDATE last_seen_at
    - Changed file   -> UPDATE metadata + version
    """

    if not path.is_file():
        return None

    extension = path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        return None

    relative_path = path.relative_to(
        DOCUMENT_ROOT
    ).as_posix()

    parts = Path(relative_path).parts

    if not parts:
        return None

    category = parts[0].lower()

    if category not in FOLDER_TO_DEPARTMENT:
        print(
            f"[SKIP] Unknown document category: {relative_path}"
        )
        return None

    checksum = calculate_sha256(path)

    document = (
        session.execute(
            select(Document).where(
                Document.relative_path == relative_path
            )
        )
        .scalar_one_or_none()
    )

    if document is None:
        department_code = FOLDER_TO_DEPARTMENT[
            category
        ]

        department = (
            session.execute(
                select(Department).where(
                    Department.code == department_code
                )
            )
            .scalar_one()
        )

        document = Document(
            document_key=build_document_key(
                relative_path
            ),
            title=get_title(path),
            filename=path.name,
            relative_path=relative_path,
            source_type=get_source_type(path),
            owner_department=department,
            checksum=checksum,
            file_size=path.stat().st_size,
            status="DISCOVERED",
            version=1,
            last_seen_at=utc_now(),
        )

        session.add(document)
        session.flush()

        apply_document_acl(
            session,
            document,
            category,
        )

        print(
            f"[NEW] {relative_path}"
        )

        return document

    # Existing file
    if document.checksum == checksum:
        document.last_seen_at = utc_now()

        print(
            f"[UNCHANGED] {relative_path}"
        )

        return document

    # File changed
    document.title = get_title(path)
    document.filename = path.name
    document.source_type = get_source_type(path)
    document.checksum = checksum
    document.file_size = path.stat().st_size
    document.version += 1
    document.status = "DISCOVERED"
    document.last_seen_at = utc_now()

    apply_document_acl(
        session,
        document,
        category,
    )

    print(
        f"[UPDATED] {relative_path} "
        f"(v{document.version})"
    )

    return document


def sync_document_directory() -> None:
    """
    Scan the complete document directory and synchronize SQL state.
    """

    if not DOCUMENT_ROOT.exists():
        raise FileNotFoundError(
            f"Document directory does not exist: "
            f"{DOCUMENT_ROOT}"
        )

    seen_paths: set[str] = set()

    with SessionLocal() as session:

        for path in DOCUMENT_ROOT.rglob("*"):

            if not path.is_file():
                continue

            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue

            relative_path = path.relative_to(
                DOCUMENT_ROOT
            ).as_posix()

            seen_paths.add(relative_path)

            register_file(
                session,
                path,
            )

        # Mark deleted/missing files.
        documents = (
            session.execute(
                select(Document)
            )
            .scalars()
            .all()
        )

        for document in documents:

            if document.status == "DELETED":
                continue

            if document.relative_path not in seen_paths:

                document.status = "DELETED"

                print(
                    f"[DELETED] "
                    f"{document.relative_path}"
                )

        session.commit()

    print("Document directory synchronization complete.")