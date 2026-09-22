from types import SimpleNamespace

from app.auth.acl import can_access


def make_role(
    role_id: int,
    global_access: bool = False,
):
    return SimpleNamespace(
        id=role_id,
        is_global_access=global_access,
    )


def make_department(department_id: int):
    return SimpleNamespace(
        id=department_id,
    )


def make_user(
    user_id: int,
    role_id: int,
    department_id: int,
    global_access: bool = False,
    active: bool = True,
):
    role = make_role(
        role_id=role_id,
        global_access=global_access,
    )

    department = make_department(
        department_id=department_id,
    )

    return SimpleNamespace(
        id=user_id,
        role_id=role_id,
        department_id=department_id,
        role=role,
        department=department,
        is_active=active,
    )


def make_document(
    scope: str,
    status: str = "READY_FOR_INGESTION",
    roles=None,
    departments=None,
    users=None,
):
    return SimpleNamespace(
        access_scope=scope,
        status=status,
        allowed_roles=roles or [],
        allowed_departments=departments or [],
        allowed_users=users or [],
    )


# ============================================================
# GLOBAL ACCESS
# ============================================================


def test_ceo_can_access_any_document():
    user = make_user(
        user_id=1,
        role_id=1,
        department_id=6,
        global_access=True,
    )

    document = make_document(
        scope="ROLE",
        roles=[],
    )

    assert can_access(user, document) is True


def test_cto_can_access_any_document():
    user = make_user(
        user_id=2,
        role_id=2,
        department_id=3,
        global_access=True,
    )

    document = make_document(
        scope="DEPARTMENT",
        departments=[],
    )

    assert can_access(user, document) is True


def test_cofounder_can_access_any_document():
    user = make_user(
        user_id=3,
        role_id=3,
        department_id=6,
        global_access=True,
    )

    document = make_document(
        scope="USER",
        users=[],
    )

    assert can_access(user, document) is True


# ============================================================
# PUBLIC
# ============================================================


def test_employee_can_access_public_document():
    user = make_user(
        user_id=9,
        role_id=9,
        department_id=6,
    )

    document = make_document(
        scope="PUBLIC",
    )

    assert can_access(user, document) is True


# ============================================================
# ROLE ACCESS
# ============================================================


def test_authorized_role_can_access():
    finance_head_role = make_role(
        role_id=4,
    )

    user = make_user(
        user_id=4,
        role_id=4,
        department_id=1,
    )

    document = make_document(
        scope="ROLE",
        roles=[
            finance_head_role,
        ],
    )

    assert can_access(user, document) is True


def test_unauthorized_role_is_denied():
    engineer_role = make_role(
        role_id=6,
    )

    user = make_user(
        user_id=6,
        role_id=6,
        department_id=3,
    )

    document = make_document(
        scope="ROLE",
        roles=[
            make_role(4),
            make_role(5),
        ],
    )

    assert can_access(user, document) is False


# ============================================================
# DEPARTMENT ACCESS
# ============================================================


def test_authorized_department_can_access():
    user = make_user(
        user_id=6,
        role_id=6,
        department_id=3,
    )

    document = make_document(
        scope="DEPARTMENT",
        departments=[
            make_department(3),
        ],
    )

    assert can_access(user, document) is True


def test_unauthorized_department_is_denied():
    user = make_user(
        user_id=6,
        role_id=6,
        department_id=3,
    )

    document = make_document(
        scope="DEPARTMENT",
        departments=[
            make_department(5),
        ],
    )

    assert can_access(user, document) is False


# ============================================================
# USER ACCESS
# ============================================================


def test_explicit_user_can_access():
    user = make_user(
        user_id=6,
        role_id=6,
        department_id=3,
    )

    document = make_document(
        scope="USER",
        users=[
            SimpleNamespace(id=6),
        ],
    )

    assert can_access(user, document) is True


def test_non_explicit_user_is_denied():
    user = make_user(
        user_id=6,
        role_id=6,
        department_id=3,
    )

    document = make_document(
        scope="USER",
        users=[
            SimpleNamespace(id=7),
        ],
    )

    assert can_access(user, document) is False


# ============================================================
# PENDING / DELETED
# ============================================================


def test_pending_policy_document_is_denied():
    user = make_user(
        user_id=1,
        role_id=1,
        department_id=6,
        global_access=True,
    )

    document = make_document(
        scope="PENDING",
        status="PENDING_POLICY",
    )

    assert can_access(user, document) is False


def test_deleted_document_is_denied():
    user = make_user(
        user_id=1,
        role_id=1,
        department_id=6,
        global_access=True,
    )

    document = make_document(
        scope="PUBLIC",
        status="DELETED",
    )

    assert can_access(user, document) is False


# ============================================================
# INACTIVE USER
# ============================================================


def test_inactive_user_is_denied():
    user = make_user(
        user_id=1,
        role_id=1,
        department_id=6,
        global_access=True,
        active=False,
    )

    document = make_document(
        scope="PUBLIC",
    )

    assert can_access(user, document) is False


# ============================================================
# FAIL CLOSED
# ============================================================


def test_unknown_scope_is_denied():
    user = make_user(
        user_id=9,
        role_id=9,
        department_id=6,
    )

    document = make_document(
        scope="UNKNOWN_SCOPE",
    )

    assert can_access(user, document) is False