from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


AccessScope = Literal[
    "PUBLIC",
    "DEPARTMENT",
    "ROLE",
    "USER",
]


Classification = Literal[
    "PUBLIC",
    "PUBLIC_INTERNAL",
    "INTERNAL",
    "CONFIDENTIAL",
    "RESTRICTED",
]


class DocumentPolicyUpdate(BaseModel):
    """
    Policy supplied by the admin frontend.
    """

    classification: Classification

    access_scope: AccessScope

    department_ids: list[int] = Field(
        default_factory=list,
    )

    role_ids: list[int] = Field(
        default_factory=list,
    )

    user_ids: list[int] = Field(
        default_factory=list,
    )

    @model_validator(mode="after")
    def validate_scope(self):
        if self.access_scope == "PUBLIC":

            if (
                self.department_ids
                or self.role_ids
                or self.user_ids
            ):
                raise ValueError(
                    "PUBLIC documents cannot have "
                    "department, role, or user ACL entries."
                )

        elif self.access_scope == "DEPARTMENT":

            if not self.department_ids:
                raise ValueError(
                    "DEPARTMENT scope requires at least "
                    "one department."
                )

            if self.role_ids or self.user_ids:
                raise ValueError(
                    "DEPARTMENT scope cannot contain "
                    "role or user ACL entries."
                )

        elif self.access_scope == "ROLE":

            if not self.role_ids:
                raise ValueError(
                    "ROLE scope requires at least one role."
                )

            if self.department_ids or self.user_ids:
                raise ValueError(
                    "ROLE scope cannot contain "
                    "department or user ACL entries."
                )

        elif self.access_scope == "USER":

            if not self.user_ids:
                raise ValueError(
                    "USER scope requires at least one user."
                )

            if self.department_ids or self.role_ids:
                raise ValueError(
                    "USER scope cannot contain "
                    "department or role ACL entries."
                )

        return self


class DocumentSummary(BaseModel):
    id: int
    document_key: str
    title: str
    filename: str
    relative_path: str
    source_type: str
    classification: str
    access_scope: str
    status: str
    version: int

    class Config:
        from_attributes = True


class PolicyOptions(BaseModel):
    roles: list[dict]
    departments: list[dict]
    users: list[dict]