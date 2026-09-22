from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import User


ADMIN_ROLES = {
    "CEO",
    "CTO",
    "COFOUNDER",
}


def get_current_user(
    x_user_email: str = Header(
        ...,
        alias="X-User-Email",
    ),
    db: Session = Depends(get_db),
) -> User:
    """
    Prototype identity resolver.

    Frontend sends:

        X-User-Email: ceo@monke.ai

    Production:
        Replace this with SSO/JWT/Entra/Google/Okta.
    """

    user = (
        db.execute(
            select(User)
            .where(
                User.email == x_user_email,
                User.is_active.is_(True),
            )
        )
        .scalar_one_or_none()
    )

    if user is None:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unknown or inactive user.",
        )

    return user


def require_policy_admin(
    current_user: User = Depends(
        get_current_user
    ),
) -> User:
    """
    Only top-level organization admins can
    assign document policies in the prototype.
    """

    if current_user.role.code not in ADMIN_ROLES:

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "You do not have permission "
                "to manage document policies."
            ),
        )

    return current_user