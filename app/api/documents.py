from __future__ import annotations

from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth.users import require_policy_admin
from app.db.audit import parse_audit_details, record_audit
from app.db.database import SessionLocal, get_db
from app.db.models import (
    AuditLog,
    Department,
    Document,
    Role,
    User,
)
from app.ingestion.file_registry import (
    DOCUMENT_ROOT,
    FOLDER_TO_DEPARTMENT,
    SUPPORTED_EXTENSIONS,
    register_file,
)
from app.ingestion.manager import get_ingestion_manager
from app.schemas.documents import (
    AuditLogResponse,
    DeleteResponse,
    DocumentDetail,
    DocumentPolicyUpdate,
    DocumentSummary,
    IngestionStatusResponse,
    PolicyOptions,
    UploadResponse,
)


router = APIRouter(
    prefix="/api/documents",
    tags=["documents"],
)

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def _identity(user: User | None) -> dict | None:
    if user is None:
        return None

    return {
        "id": user.id,
        "email": user.email,
        "name": user.full_name,
        "role": user.role.code,
        "department": user.department.code,
    }


def _load_document(
    db: Session,
    document_id: int,
) -> Document | None:
    return db.execute(
        select(Document)
        .options(
            selectinload(Document.owner_department),
            selectinload(Document.allowed_roles),
            selectinload(Document.allowed_departments),
            selectinload(Document.allowed_users),
            selectinload(Document.created_by_user),
            selectinload(Document.policy_updated_by_user),
            selectinload(Document.deleted_by_user),
            selectinload(Document.audit_logs).selectinload(
                AuditLog.actor_user
            ),
        )
        .where(Document.id == document_id)
    ).unique().scalar_one_or_none()


def _summary(document: Document) -> DocumentSummary:
    return DocumentSummary(
        id=document.id,
        document_key=document.document_key,
        title=document.title,
        filename=document.filename,
        relative_path=document.relative_path,
        source_type=document.source_type,
        classification=document.classification,
        access_scope=document.access_scope,
        status=document.status,
        version=document.version,
        file_size=document.file_size,
        checksum=document.checksum,
        created_at=document.created_at.isoformat(),
        updated_at=document.updated_at.isoformat(),
        indexed_at=_iso(document.indexed_at),
        last_seen_at=_iso(document.last_seen_at),
        created_by=_identity(document.created_by_user),
        policy_updated_by=_identity(document.policy_updated_by_user),
        policy_updated_at=_iso(document.policy_updated_at),
        deleted_by=_identity(document.deleted_by_user),
        deleted_at=_iso(document.deleted_at),
        owner_department={
            "id": document.owner_department.id,
            "code": document.owner_department.code,
            "name": document.owner_department.name,
        },
    )


def _detail(document: Document) -> DocumentDetail:
    summary = _summary(document)
    audit_logs = []

    for log in sorted(
        document.audit_logs,
        key=lambda item: item.created_at,
        reverse=True,
    ):
        audit_logs.append(
            AuditLogResponse(
                id=log.id,
                action=log.action,
                actor=_identity(log.actor_user),
                details=parse_audit_details(log.details_json),
                created_at=log.created_at.isoformat(),
            )
        )

    path = (DOCUMENT_ROOT / Path(document.relative_path)).resolve()
    root = DOCUMENT_ROOT.resolve()

    if root not in path.parents:
        exists = False
        safe_path = None
    else:
        exists = path.is_file()
        safe_path = str(path)

    return DocumentDetail(
        **summary.model_dump(),
        acl={
            "roles": [
                {
                    "id": role.id,
                    "code": role.code,
                    "name": role.name,
                }
                for role in document.allowed_roles
            ],
            "departments": [
                {
                    "id": department.id,
                    "code": department.code,
                    "name": department.name,
                }
                for department in document.allowed_departments
            ],
            "users": [
                {
                    "id": user.id,
                    "employee_code": user.employee_code,
                    "name": user.full_name,
                    "email": user.email,
                    "role": user.role.code,
                    "department": user.department.code,
                }
                for user in document.allowed_users
            ],
        },
        audit_logs=audit_logs,
        filesystem={
            "path": safe_path,
            "relative_path": document.relative_path,
            "exists": exists,
            "size_bytes": path.stat().st_size if exists else 0,
        },
    )


def _validate_document_path(path: Path) -> None:
    root = DOCUMENT_ROOT.resolve()
    resolved = path.resolve()
    if root not in resolved.parents:
        raise HTTPException(
            status_code=400,
            detail="Invalid document path.",
        )


async def _write_upload(
    upload: UploadFile,
    target: Path,
) -> int:
    written = 0

    with target.open("wb") as output:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break

            written += len(chunk)

            if written > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=(
                        "Upload exceeds the 50 MB prototype limit."
                    ),
                )

            output.write(chunk)

    return written


# ============================================================
# ADMIN DOCUMENT LIST / OPTIONS
# ============================================================


@router.get(
    "",
    response_model=list[DocumentSummary],
)
def list_documents(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_policy_admin),
):
    stmt = (
        select(Document)
        .options(
            selectinload(Document.owner_department),
            selectinload(Document.created_by_user),
            selectinload(Document.policy_updated_by_user),
            selectinload(Document.deleted_by_user),
        )
        .order_by(Document.updated_at.desc())
    )

    if status:
        stmt = stmt.where(Document.status == status)

    documents = (
        db.execute(stmt)
        .scalars()
        .all()
    )

    return [
        _summary(document)
        for document in documents
    ]


@router.get(
    "/policy-options",
    response_model=PolicyOptions,
)
def get_policy_options(
    db: Session = Depends(get_db),
    _: User = Depends(require_policy_admin),
):
    roles = db.execute(
        select(Role).order_by(Role.name)
    ).scalars().all()

    departments = db.execute(
        select(Department).order_by(Department.name)
    ).scalars().all()

    users = db.execute(
        select(User)
        .where(User.is_active.is_(True))
        .order_by(User.full_name)
    ).scalars().all()

    return PolicyOptions(
        roles=[
            {
                "id": role.id,
                "code": role.code,
                "name": role.name,
                "is_global_access": role.is_global_access,
            }
            for role in roles
        ],
        departments=[
            {
                "id": department.id,
                "code": department.code,
                "name": department.name,
            }
            for department in departments
        ],
        users=[
            {
                "id": user.id,
                "employee_code": user.employee_code,
                "name": user.full_name,
                "email": user.email,
                "role": user.role.code,
                "department": user.department.code,
            }
            for user in users
        ],
    )


# ============================================================
# BACKGROUND INGESTION STATUS
# ============================================================


@router.get(
    "/ingestion/status",
    response_model=IngestionStatusResponse,
)
def ingestion_status(
    _: User = Depends(require_policy_admin),
):
    return get_ingestion_manager().snapshot()


# ============================================================
# UPLOAD
# ============================================================


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    category: str = Form(...),
    db: Session = Depends(get_db),
    admin: User = Depends(require_policy_admin),
):
    category = category.strip().lower()

    if category not in FOLDER_TO_DEPARTMENT:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid category. Allowed: "
                + ", ".join(sorted(FOLDER_TO_DEPARTMENT))
            ),
        )

    filename = Path(file.filename or "").name

    if not filename or filename in {".", ".."}:
        raise HTTPException(
            status_code=400,
            detail="A valid filename is required.",
        )

    extension = Path(filename).suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported file type. Allowed: "
                + ", ".join(sorted(SUPPORTED_EXTENSIONS))
            ),
        )

    category_dir = DOCUMENT_ROOT / category
    category_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    target = category_dir / filename
    _validate_document_path(target)

    if target.exists():
        raise HTTPException(
            status_code=409,
            detail=(
                f"A file named '{filename}' already exists in "
                f"the {category} folder."
            ),
        )

    try:
        await _write_upload(
            file,
            target,
        )

        document = register_file(
            db,
            target,
            created_by_user_id=admin.id,
            actor_user_id=admin.id,
        )

        if document is None:
            raise HTTPException(
                status_code=400,
                detail="The uploaded file could not be registered.",
            )

        document.created_by_user_id = admin.id

        record_audit(
            db,
            action="UPLOADED",
            actor_user_id=admin.id,
            document_id=document.id,
            details={
                "filename": document.filename,
                "relative_path": document.relative_path,
                "category": category,
                "owner_department": document.owner_department.code,
                "initial_access_scope": document.access_scope,
            },
        )

        db.commit()
        db.refresh(document)

    except HTTPException:
        if target.exists():
            target.unlink(missing_ok=True)
        raise
    except Exception:
        if target.exists():
            target.unlink(missing_ok=True)
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Upload failed while registering the document.",
        )

    document = _load_document(
        db,
        document.id,
    )

    assert document is not None

    return UploadResponse(
        document=_detail(document),
        ingestion_queued=False,
    )


# ============================================================
# DOCUMENT DETAILS
# ============================================================


@router.get(
    "/{document_id}",
    response_model=DocumentDetail,
)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_policy_admin),
):
    document = _load_document(
        db,
        document_id,
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    return _detail(document)


# ============================================================
# POLICY UPDATE / APPROVAL
# ============================================================


@router.patch(
    "/{document_id}/policy",
    response_model=DocumentDetail,
)
def update_document_policy(
    document_id: int,
    policy: DocumentPolicyUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_policy_admin),
):
    document = _load_document(
        db,
        document_id,
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    if document.status == "DELETED":
        raise HTTPException(
            status_code=409,
            detail="Deleted documents cannot receive an access policy.",
        )

    departments: list[Department] = []
    roles: list[Role] = []
    users: list[User] = []

    if policy.department_ids:
        departments = db.execute(
            select(Department).where(
                Department.id.in_(policy.department_ids)
            )
        ).scalars().all()

        found = {item.id for item in departments}
        missing = set(policy.department_ids) - found
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown department IDs: {sorted(missing)}",
            )

    if policy.role_ids:
        roles = db.execute(
            select(Role).where(
                Role.id.in_(policy.role_ids)
            )
        ).scalars().all()

        found = {item.id for item in roles}
        missing = set(policy.role_ids) - found
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown role IDs: {sorted(missing)}",
            )

    if policy.user_ids:
        users = db.execute(
            select(User)
            .where(User.id.in_(policy.user_ids))
        ).scalars().all()

        found = {item.id for item in users}
        missing = set(policy.user_ids) - found
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown user IDs: {sorted(missing)}",
            )

    previous_policy = {
        "classification": document.classification,
        "access_scope": document.access_scope,
        "role_ids": [role.id for role in document.allowed_roles],
        "department_ids": [
            department.id
            for department in document.allowed_departments
        ],
        "user_ids": [user.id for user in document.allowed_users],
    }

    document.allowed_departments.clear()
    document.allowed_roles.clear()
    document.allowed_users.clear()

    document.classification = policy.classification
    document.access_scope = policy.access_scope

    if policy.access_scope == "DEPARTMENT":
        document.allowed_departments.extend(departments)
    elif policy.access_scope == "ROLE":
        document.allowed_roles.extend(roles)
    elif policy.access_scope == "USER":
        document.allowed_users.extend(users)

    document.policy_updated_by_user_id = admin.id
    from datetime import datetime, timezone
    document.policy_updated_at = datetime.now(timezone.utc)
    document.status = "READY_FOR_INGESTION"

    record_audit(
        db,
        action="POLICY_UPDATED",
        actor_user_id=admin.id,
        document_id=document.id,
        details={
            "previous": previous_policy,
            "new": {
                "classification": policy.classification,
                "access_scope": policy.access_scope,
                "role_ids": policy.role_ids,
                "department_ids": policy.department_ids,
                "user_ids": policy.user_ids,
            },
        },
    )

    db.commit()
    db.refresh(document)

    queued = get_ingestion_manager().enqueue_index(
        document.id
    )

    document = _load_document(db, document.id)
    assert document is not None

    detail = _detail(document)
    # Keep queue information visible to the frontend through the audit/state;
    # actual background processing status is available from /ingestion/status.
    _ = queued
    return detail


# ============================================================
# MANUAL REINDEX
# ============================================================


@router.post(
    "/{document_id}/reindex",
    response_model=DocumentDetail,
)
def reindex_document(
    document_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_policy_admin),
):
    document = db.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    if document.status == "DELETED":
        raise HTTPException(
            status_code=409,
            detail="Deleted documents cannot be reindexed.",
        )

    if document.access_scope == "PENDING":
        raise HTTPException(
            status_code=409,
            detail="Approve a policy before indexing this document.",
        )

    document.status = "READY_FOR_INGESTION"

    record_audit(
        db,
        action="REINDEX_REQUESTED",
        actor_user_id=admin.id,
        document_id=document.id,
        details={"status": "READY_FOR_INGESTION"},
    )

    db.commit()

    get_ingestion_manager().enqueue_index(
        document.id
    )

    refreshed = _load_document(db, document.id)
    assert refreshed is not None
    return _detail(refreshed)


# ============================================================
# DELETE / ARCHIVE FILE
# ============================================================


@router.delete(
    "/{document_id}",
    response_model=DeleteResponse,
)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_policy_admin),
):
    document = db.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    path = (DOCUMENT_ROOT / Path(document.relative_path)).resolve()
    _validate_document_path(path)

    # Revoke retrieval access in SQL first. This is the security boundary;
    # physical file removal and vector/BM25 cleanup happen afterward.
    from datetime import datetime, timezone

    document.status = "DELETED"
    document.deleted_by_user_id = admin.id
    document.deleted_at = datetime.now(timezone.utc)

    record_audit(
        db,
        action="DELETE_REQUESTED",
        actor_user_id=admin.id,
        document_id=document.id,
        details={
            "relative_path": document.relative_path,
            "file_exists_at_request": path.is_file(),
        },
    )

    db.commit()

    file_removed = False
    file_remove_error: str | None = None

    if path.exists():
        try:
            path.unlink()
            file_removed = True
        except OSError as exc:
            file_remove_error = str(exc)

            with SessionLocal() as audit_db:
                record_audit(
                    audit_db,
                    action="DELETE_FILE_FAILED",
                    actor_user_id=admin.id,
                    document_id=document.id,
                    details={
                        "relative_path": document.relative_path,
                        "error": file_remove_error,
                    },
                )
                audit_db.commit()

    else:
        file_removed = True

    cleanup_queued = get_ingestion_manager().enqueue_delete(
        document.id
    )

    if file_remove_error:
        detail = (
            "Document access has been revoked, but the physical file "
            f"could not be removed: {file_remove_error}"
        )
        # Return a conflict only after the secure SQL state has been committed.
        raise HTTPException(
            status_code=409,
            detail=detail,
        )

    return DeleteResponse(
        document_id=document.id,
        status="DELETED",
        file_removed=file_removed,
        index_cleanup_queued=cleanup_queued,
    )
