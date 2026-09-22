from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.db.database import SessionLocal
from app.db.models import Department, Document


# ============================================================
# PATH CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DOCUMENT_ROOT = (
    PROJECT_ROOT / "data" / "documents"
).resolve()


# ============================================================
# SUPPORTED FILE TYPES
# ============================================================

SUPPORTED_EXTENSIONS = {
    ".pdf": "PDF",
    ".docx": "DOCX",
    ".xlsx": "XLSX",
    ".csv": "CSV",
    ".txt": "TXT",
    ".md": "MARKDOWN",
}


# ============================================================
# DOCUMENT FOLDER → OWNER DEPARTMENT
#
# IMPORTANT:
# This mapping determines ownership only.
# It does NOT determine access permissions.
# ============================================================

FOLDER_TO_DEPARTMENT = {
    "finance": "FIN",
    "hr": "HR",
    "technology": "TECH",
    "management": "MGT",
    "marketing": "MKT",
    "public": "GENERAL",
}


# ============================================================
# DOCUMENT STATES
# ============================================================

STATUS_PENDING_POLICY = "PENDING_POLICY"
STATUS_READY_FOR_INGESTION = "READY_FOR_INGESTION"
STATUS_INDEXING = "INDEXING"
STATUS_INDEXED = "INDEXED"
STATUS_FAILED = "FAILED"
STATUS_DELETED = "DELETED"


# ============================================================
# ACCESS SCOPE STATES
# ============================================================

ACCESS_PENDING = "PENDING"
ACCESS_PUBLIC = "PUBLIC"
ACCESS_DEPARTMENT = "DEPARTMENT"
ACCESS_ROLE = "ROLE"
ACCESS_USER = "USER"


# ============================================================
# HELPERS
# ============================================================

def utc_now() -> datetime:
    """
    Return the current UTC timestamp.
    """
    return datetime.now(timezone.utc)


def calculate_sha256(path: Path) -> str:
    """
    Calculate a SHA-256 checksum for a file.

    The checksum allows us to determine whether the file's
    contents have actually changed.
    """

    digest = hashlib.sha256()

    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)

    return digest.hexdigest()


def get_source_type(path: Path) -> str:
    """
    Convert a file extension into a normalized source type.
    """

    return SUPPORTED_EXTENSIONS.get(
        path.suffix.lower(),
        "UNKNOWN",
    )


def build_document_key(relative_path: str) -> str:
    """
    Create a stable application-level identifier.

    Example:

        finance/q2_report.pdf

    becomes something like:

        DOC-a8f2c4...
    """

    digest = hashlib.sha256(
        relative_path.encode("utf-8")
    ).hexdigest()

    return f"DOC-{digest[:20]}"


def get_title(path: Path) -> str:
    """
    Convert a filename into a human-readable title.

    Example:

        Q2_financial_review.pdf

    becomes:

        Q2 Financial Review
    """

    return (
        path.stem
        .replace("_", " ")
        .replace("-", " ")
        .strip()
    )


def get_owner_department(
    session,
    category: str,
) -> Department:
    """
    Determine the owning department from the document folder.

    NOTE:
        Folder location determines ownership metadata only.
        It does NOT grant access.
    """

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
        .scalar_one_or_none()
    )

    if department is None:
        raise ValueError(
            f"Department '{department_code}' "
            f"does not exist in the database."
        )

    return department


# ============================================================
# FILE REGISTRATION
# ============================================================

def register_file(
    session,
    path: Path,
) -> Document | None:
    """
    Register or synchronize a single document.

    New file:
        PENDING_POLICY

    Existing unchanged file:
        Update last_seen_at only.

    Existing changed file:
        Preserve its ACL.
        Mark it READY_FOR_INGESTION if a policy already exists.
        Otherwise keep it PENDING_POLICY.

    Reappeared deleted file:
        Restore it and send it back through ingestion.
    """

    # --------------------------------------------------------
    # Basic validation
    # --------------------------------------------------------

    if not path.is_file():
        return None

    extension = path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        return None

    # --------------------------------------------------------
    # Resolve relative path
    # --------------------------------------------------------

    try:
        relative_path = path.relative_to(
            DOCUMENT_ROOT
        ).as_posix()

    except ValueError:
        print(
            f"[SKIP] File outside document root: {path}"
        )
        return None

    parts = Path(relative_path).parts

    if not parts:
        return None

    # First directory is treated as category.
    category = parts[0].lower()

    if category not in FOLDER_TO_DEPARTMENT:
        print(
            f"[SKIP] Unknown document category: "
            f"{relative_path}"
        )
        return None

    # --------------------------------------------------------
    # Calculate current file information
    # --------------------------------------------------------

    checksum = calculate_sha256(path)

    file_size = path.stat().st_size

    source_type = get_source_type(path)

    title = get_title(path)

    now = utc_now()

    # --------------------------------------------------------
    # Find existing document
    # --------------------------------------------------------

    document = (
        session.execute(
            select(Document).where(
                Document.relative_path == relative_path
            )
        )
        .scalar_one_or_none()
    )

    # ========================================================
    # NEW FILE
    # ========================================================

    if document is None:

        owner_department = get_owner_department(
            session,
            category,
        )

        document = Document(
            document_key=build_document_key(
                relative_path
            ),
            title=title,
            filename=path.name,
            relative_path=relative_path,
            source_type=source_type,

            owner_department=owner_department,

            # Newly discovered files do not get trusted
            # access permissions automatically.
            classification="INTERNAL",
            access_scope=ACCESS_PENDING,

            checksum=checksum,
            file_size=file_size,

            status=STATUS_PENDING_POLICY,

            version=1,

            last_seen_at=now,
        )

        session.add(document)
        session.flush()

        print(
            f"[NEW] {relative_path} "
            f"→ {STATUS_PENDING_POLICY}"
        )

        return document

    # ========================================================
    # EXISTING FILE - UNCHANGED
    # ========================================================

    if document.checksum == checksum:

        # If a previously deleted file reappears,
        # it must become active again.
        if document.status == STATUS_DELETED:

            if document.access_scope == ACCESS_PENDING:
                document.status = STATUS_PENDING_POLICY
            else:
                document.status = STATUS_READY_FOR_INGESTION

            print(
                f"[RESTORED] {relative_path} "
                f"→ {document.status}"
            )

        else:

            print(
                f"[UNCHANGED] {relative_path}"
            )

        document.last_seen_at = now

        return document

    # ========================================================
    # EXISTING FILE - CONTENT CHANGED
    # ========================================================

    document.title = title

    document.filename = path.name

    document.source_type = source_type

    document.checksum = checksum

    document.file_size = file_size

    document.version += 1

    document.last_seen_at = now

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # The existing ACL remains unchanged.
    #
    # If the document already has an approved policy,
    # it can go directly back to ingestion.
    #
    # If the document somehow still has PENDING access,
    # do not let the changed file bypass policy review.
    # --------------------------------------------------------

    if document.access_scope == ACCESS_PENDING:

        document.status = STATUS_PENDING_POLICY

        print(
            f"[UPDATED] {relative_path} "
            f"(v{document.version}) "
            f"→ {STATUS_PENDING_POLICY}"
        )

    else:

        document.status = STATUS_READY_FOR_INGESTION

        print(
            f"[UPDATED] {relative_path} "
            f"(v{document.version}) "
            f"→ {STATUS_READY_FOR_INGESTION}"
        )

    return document


# ============================================================
# DIRECTORY SYNCHRONIZATION
# ============================================================

def sync_document_directory() -> None:
    """
    Scan data/documents/ and synchronize the SQL document registry.

    Responsibilities:

        filesystem
            ↓
        document discovery
            ↓
        SQL registration/update
            ↓
        deletion detection
    """

    if not DOCUMENT_ROOT.exists():

        raise FileNotFoundError(
            "Document directory does not exist: "
            f"{DOCUMENT_ROOT}"
        )

    seen_paths: set[str] = set()

    with SessionLocal() as session:

        # ----------------------------------------------------
        # Discover files
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Detect deleted files
        # ----------------------------------------------------

        documents = (
            session.execute(
                select(Document)
            )
            .scalars()
            .all()
        )

        for document in documents:

            if (
                document.relative_path
                not in seen_paths
            ):

                if document.status != STATUS_DELETED:

                    document.status = STATUS_DELETED

                    print(
                        f"[DELETED] "
                        f"{document.relative_path}"
                    )

        # ----------------------------------------------------
        # Persist all changes
        # ----------------------------------------------------

        session.commit()

    print(
        "Document directory synchronization complete."
    )