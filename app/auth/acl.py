from __future__ import annotations

from app.db.models import Document, User


# ============================================================
# ACCESS SCOPES
# ============================================================

ACCESS_PENDING = "PENDING"
ACCESS_PUBLIC = "PUBLIC"
ACCESS_DEPARTMENT = "DEPARTMENT"
ACCESS_ROLE = "ROLE"
ACCESS_USER = "USER"


# ============================================================
# DOCUMENT STATUSES
# ============================================================

STATUS_PENDING_POLICY = "PENDING_POLICY"
STATUS_DELETED = "DELETED"


# ============================================================
# CORE AUTHORIZATION
# ============================================================


def can_access(
    user: User,
    document: Document,
) -> bool:
    """
    Determine whether a user is allowed to access a document.

    Authorization rules:

    1. Invalid / inactive users are denied.
    2. Documents without an approved policy are denied.
    3. Deleted documents are denied.
    4. Global-access roles (CEO / CTO / COFOUNDER)
       can access all active documents.
    5. PUBLIC documents are accessible to all active users.
    6. ROLE documents require a matching role.
    7. DEPARTMENT documents require a matching department.
    8. USER documents require an explicit user grant.
    9. Unknown access scopes fail closed.

    This function only performs authorization.
    It does not perform:
        - vector search
        - document retrieval
        - embedding
        - LLM calls
        - citation generation
    """

    # --------------------------------------------------------
    # 1. Validate user/document
    # --------------------------------------------------------

    if user is None:
        return False

    if document is None:
        return False

    # --------------------------------------------------------
    # 2. User must be active
    # --------------------------------------------------------

    if not user.is_active:
        return False

    # --------------------------------------------------------
    # 3. Document must have an approved access policy
    # --------------------------------------------------------

    if document.access_scope == ACCESS_PENDING:
        return False

    if document.status == STATUS_PENDING_POLICY:
        return False

    # --------------------------------------------------------
    # 4. Deleted documents are never accessible
    # --------------------------------------------------------

    if document.status == STATUS_DELETED:
        return False

    # --------------------------------------------------------
    # 5. Global-access roles
    #
    # CEO / CTO / COFOUNDER currently have:
    #
    #     role.is_global_access = True
    #
    # These users can access every active document.
    # --------------------------------------------------------

    if user.role.is_global_access:
        return True

    # --------------------------------------------------------
    # 6. PUBLIC documents
    # --------------------------------------------------------

    if document.access_scope == ACCESS_PUBLIC:
        return True

    # --------------------------------------------------------
    # 7. ROLE-based access
    # --------------------------------------------------------

    if document.access_scope == ACCESS_ROLE:

        return any(
            role.id == user.role_id
            for role in document.allowed_roles
        )

    # --------------------------------------------------------
    # 8. DEPARTMENT-based access
    # --------------------------------------------------------

    if document.access_scope == ACCESS_DEPARTMENT:

        return any(
            department.id == user.department_id
            for department in document.allowed_departments
        )

    # --------------------------------------------------------
    # 9. USER-specific access
    # --------------------------------------------------------

    if document.access_scope == ACCESS_USER:

        return any(
            allowed_user.id == user.id
            for allowed_user in document.allowed_users
        )

    # --------------------------------------------------------
    # 10. Unknown scope
    #
    # Security principle:
    # unknown authorization states must fail closed.
    # --------------------------------------------------------

    return False


# ============================================================
# ACCESS EXPLANATION
# ============================================================


def explain_access(
    user: User,
    document: Document,
) -> tuple[bool, str]:
    """
    Return:

        (allowed, reason)

    This is useful for:
        - debugging
        - unit tests
        - development
        - admin tooling

    Do not expose detailed authorization reasons directly
    to normal users in production because they may reveal
    internal permission information.
    """

    # --------------------------------------------------------
    # Validate input
    # --------------------------------------------------------

    if user is None:
        return False, "No user provided."

    if document is None:
        return False, "No document provided."

    # --------------------------------------------------------
    # User state
    # --------------------------------------------------------

    if not user.is_active:
        return False, "User is inactive."

    # --------------------------------------------------------
    # Document policy state
    # --------------------------------------------------------

    if document.access_scope == ACCESS_PENDING:
        return False, "Document has no approved access policy."

    if document.status == STATUS_PENDING_POLICY:
        return False, "Document policy is pending."

    if document.status == STATUS_DELETED:
        return False, "Document has been deleted."

    # --------------------------------------------------------
    # Global role
    # --------------------------------------------------------

    if user.role.is_global_access:
        return True, "User has global-access role."

    # --------------------------------------------------------
    # Public document
    # --------------------------------------------------------

    if document.access_scope == ACCESS_PUBLIC:
        return True, "Document is public."

    # --------------------------------------------------------
    # Role access
    # --------------------------------------------------------

    if document.access_scope == ACCESS_ROLE:

        if any(
            role.id == user.role_id
            for role in document.allowed_roles
        ):
            return True, "User role is authorized."

        return False, "User role is not authorized."

    # --------------------------------------------------------
    # Department access
    # --------------------------------------------------------

    if document.access_scope == ACCESS_DEPARTMENT:

        if any(
            department.id == user.department_id
            for department in document.allowed_departments
        ):
            return True, "User department is authorized."

        return False, "User department is not authorized."

    # --------------------------------------------------------
    # User-specific access
    # --------------------------------------------------------

    if document.access_scope == ACCESS_USER:

        if any(
            allowed_user.id == user.id
            for allowed_user in document.allowed_users
        ):
            return True, "User is explicitly authorized."

        return False, "User is not explicitly authorized."

    # --------------------------------------------------------
    # Unknown scope
    # --------------------------------------------------------

    return False, "Unknown access scope."