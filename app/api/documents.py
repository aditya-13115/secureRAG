from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.users import require_policy_admin
from app.db.database import get_db
from app.db.models import (
    Department,
    Document,
    Role,
    User,
)
from app.schemas.documents import (
    DocumentPolicyUpdate,
    DocumentSummary,
    PolicyOptions,
)


router = APIRouter(
    prefix="/api/documents",
    tags=["documents"],
)


# ============================================================
# LIST DOCUMENTS
# ============================================================


@router.get(
    "",
    response_model=list[DocumentSummary],
)
def list_documents(
    status: str | None = Query(
        default=None,
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_policy_admin),
):
    """
    Admin-only document listing.

    Examples:

        GET /api/documents

        GET /api/documents?status=PENDING_POLICY
    """

    stmt = select(Document).order_by(
        Document.created_at.desc()
    )

    if status:
        stmt = stmt.where(
            Document.status == status
        )

    documents = (
        db.execute(stmt)
        .scalars()
        .all()
    )

    return documents


# ============================================================
# POLICY OPTIONS
# ============================================================


@router.get(
    "/policy-options",
    response_model=PolicyOptions,
)
def get_policy_options(
    db: Session = Depends(get_db),
    _: User = Depends(require_policy_admin),
):
    """
    Data required by the admin frontend
    to construct policy dropdowns/multiselects.
    """

    roles = (
        db.execute(
            select(Role)
            .order_by(Role.name)
        )
        .scalars()
        .all()
    )

    departments = (
        db.execute(
            select(Department)
            .order_by(Department.name)
        )
        .scalars()
        .all()
    )

    users = (
        db.execute(
            select(User)
            .where(User.is_active.is_(True))
            .order_by(User.full_name)
        )
        .scalars()
        .all()
    )

    return PolicyOptions(
        roles=[
            {
                "id": role.id,
                "code": role.code,
                "name": role.name,
                "is_global_access": (
                    role.is_global_access
                ),
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
# GET ONE DOCUMENT
# ============================================================


@router.get(
    "/{document_id}",
    response_model=DocumentSummary,
)
def get_document(
    document_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_policy_admin),
):
    document = db.get(
        Document,
        document_id,
    )

    if document is None:

        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    return document


# ============================================================
# ASSIGN / UPDATE POLICY
# ============================================================


@router.patch(
    "/{document_id}/policy",
    response_model=DocumentSummary,
)
def update_document_policy(
    document_id: int,
    policy: DocumentPolicyUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_policy_admin),
):
    """
    Assign or update the access policy for a document.

    After successful policy assignment:

        status = READY_FOR_INGESTION

    The ingestion worker can then pick it up.
    """

    document = db.get(
        Document,
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
            detail=(
                "Deleted documents cannot receive "
                "an access policy."
            ),
        )

    # ========================================================
    # Verify referenced IDs
    # ========================================================

    departments = []

    roles = []

    users = []

    if policy.department_ids:

        departments = (
            db.execute(
                select(Department).where(
                    Department.id.in_(
                        policy.department_ids
                    )
                )
            )
            .scalars()
            .all()
        )

        found_ids = {
            department.id
            for department in departments
        }

        missing = (
            set(policy.department_ids)
            - found_ids
        )

        if missing:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unknown department IDs: "
                    f"{sorted(missing)}"
                ),
            )

    if policy.role_ids:

        roles = (
            db.execute(
                select(Role).where(
                    Role.id.in_(
                        policy.role_ids
                    )
                )
            )
            .scalars()
            .all()
        )

        found_ids = {
            role.id
            for role in roles
        }

        missing = (
            set(policy.role_ids)
            - found_ids
        )

        if missing:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unknown role IDs: "
                    f"{sorted(missing)}"
                ),
            )

    if policy.user_ids:

        users = (
            db.execute(
                select(User).where(
                    User.id.in_(
                        policy.user_ids
                    )
                )
            )
            .scalars()
            .all()
        )

        found_ids = {
            user.id
            for user in users
        }

        missing = (
            set(policy.user_ids)
            - found_ids
        )

        if missing:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unknown user IDs: "
                    f"{sorted(missing)}"
                ),
            )

    # ========================================================
    # Clear existing ACL
    # ========================================================

    document.allowed_departments.clear()

    document.allowed_roles.clear()

    document.allowed_users.clear()

    # ========================================================
    # Apply new policy
    # ========================================================

    document.classification = (
        policy.classification
    )

    document.access_scope = (
        policy.access_scope
    )

    if policy.access_scope == "DEPARTMENT":

        document.allowed_departments.extend(
            departments
        )

    elif policy.access_scope == "ROLE":

        document.allowed_roles.extend(
            roles
        )

    elif policy.access_scope == "USER":

        document.allowed_users.extend(
            users
        )

    # ========================================================
    # Make document available for ingestion
    # ========================================================

    document.status = "READY_FOR_INGESTION"

    db.commit()

    db.refresh(document)

    print(
        f"[POLICY] "
        f"Admin={admin.email} "
        f"Document={document.document_key} "
        f"Scope={document.access_scope}"
    )

    return document