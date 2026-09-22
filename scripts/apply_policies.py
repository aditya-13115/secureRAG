from __future__ import annotations

import requests


BASE_URL = "http://127.0.0.1:8000"
ADMIN_EMAIL = "ceo@monke.ai"


def apply_policy(
    document_id: int,
    classification: str,
    access_scope: str,
    role_ids: list[int] | None = None,
    department_ids: list[int] | None = None,
    user_ids: list[int] | None = None,
):
    payload = {
        "classification": classification,
        "access_scope": access_scope,
        "role_ids": role_ids or [],
        "department_ids": department_ids or [],
        "user_ids": user_ids or [],
    }

    response = requests.patch(
        f"{BASE_URL}/api/documents/{document_id}/policy",
        headers={
            "X-User-Email": ADMIN_EMAIL,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=10,
    )

    if response.ok:
        data = response.json()

        print(
            f"[OK] {document_id:02d} | "
            f"{data['relative_path']} | "
            f"{data['access_scope']} | "
            f"{data['status']}"
        )

    else:
        print(
            f"[ERROR] {document_id:02d} | "
            f"{response.status_code} | "
            f"{response.text}"
        )


def main():
    # --------------------------------------------------------
    # Finance
    # CEO + CTO + COFOUNDER + FINANCE_HEAD + HR_HEAD
    # Role IDs: 1,2,3,4,5
    # --------------------------------------------------------

    for document_id in range(1, 7):
        apply_policy(
            document_id=document_id,
            classification="CONFIDENTIAL",
            access_scope="ROLE",
            role_ids=[1, 2, 3, 4, 5],
        )

    # --------------------------------------------------------
    # HR
    # CEO + CTO + COFOUNDER + FINANCE_HEAD + HR_HEAD
    # --------------------------------------------------------

    for document_id in range(7, 13):
        apply_policy(
            document_id=document_id,
            classification="CONFIDENTIAL",
            access_scope="ROLE",
            role_ids=[1, 2, 3, 4, 5],
        )

    # --------------------------------------------------------
    # Management
    # Department ID = 4
    # --------------------------------------------------------

    for document_id in range(13, 19):
        apply_policy(
            document_id=document_id,
            classification="INTERNAL",
            access_scope="DEPARTMENT",
            department_ids=[4],
        )

    # --------------------------------------------------------
    # Marketing internal
    # IDs 19,20,22
    # Department ID = 5
    # --------------------------------------------------------

    for document_id in [19, 20, 22]:
        apply_policy(
            document_id=document_id,
            classification="INTERNAL",
            access_scope="DEPARTMENT",
            department_ids=[5],
        )

    # --------------------------------------------------------
    # Marketing public
    # Everyone
    # IDs 21,23,24
    # --------------------------------------------------------

    for document_id in [21, 23, 24]:
        apply_policy(
            document_id=document_id,
            classification="PUBLIC_INTERNAL",
            access_scope="PUBLIC",
        )

    # --------------------------------------------------------
    # Public
    # Everyone
    # IDs 25-30
    # --------------------------------------------------------

    for document_id in range(25, 31):
        apply_policy(
            document_id=document_id,
            classification="PUBLIC_INTERNAL",
            access_scope="PUBLIC",
        )

    # --------------------------------------------------------
    # Technology
    # Department ID = 3
    # --------------------------------------------------------

    for document_id in range(31, 37):
        apply_policy(
            document_id=document_id,
            classification="INTERNAL",
            access_scope="DEPARTMENT",
            department_ids=[3],
        )


if __name__ == "__main__":
    main()