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
    """Policy supplied by an admin frontend."""

    classification: Classification
    access_scope: AccessScope
    department_ids: list[int] = Field(default_factory=list)
    role_ids: list[int] = Field(default_factory=list)
    user_ids: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_scope(self):
        if self.access_scope == "PUBLIC":
            if self.department_ids or self.role_ids or self.user_ids:
                raise ValueError(
                    "PUBLIC documents cannot have department, role, or user ACL entries."
                )

        elif self.access_scope == "DEPARTMENT":
            if not self.department_ids:
                raise ValueError(
                    "DEPARTMENT scope requires at least one department."
                )
            if self.role_ids or self.user_ids:
                raise ValueError(
                    "DEPARTMENT scope cannot contain role or user ACL entries."
                )

        elif self.access_scope == "ROLE":
            if not self.role_ids:
                raise ValueError(
                    "ROLE scope requires at least one role."
                )
            if self.department_ids or self.user_ids:
                raise ValueError(
                    "ROLE scope cannot contain department or user ACL entries."
                )

        elif self.access_scope == "USER":
            if not self.user_ids:
                raise ValueError(
                    "USER scope requires at least one user."
                )
            if self.department_ids or self.role_ids:
                raise ValueError(
                    "USER scope cannot contain department or role ACL entries."
                )

        return self


class IdentitySummary(BaseModel):
    id: int
    email: str
    name: str
    role: str
    department: str


class ACLSummary(BaseModel):
    roles: list[dict]
    departments: list[dict]
    users: list[dict]


class AuditLogResponse(BaseModel):
    id: int
    action: str
    actor: IdentitySummary | None
    details: dict
    created_at: str


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
    file_size: int
    checksum: str
    created_at: str
    updated_at: str
    indexed_at: str | None
    last_seen_at: str | None
    created_by: IdentitySummary | None = None
    policy_updated_by: IdentitySummary | None = None
    policy_updated_at: str | None = None
    deleted_by: IdentitySummary | None = None
    deleted_at: str | None = None
    owner_department: dict


class DocumentDetail(DocumentSummary):
    acl: ACLSummary
    audit_logs: list[AuditLogResponse]
    filesystem: dict


class UploadResponse(BaseModel):
    document: DocumentDetail
    ingestion_queued: bool


class DeleteResponse(BaseModel):
    document_id: int
    status: str
    file_removed: bool
    index_cleanup_queued: bool


class PolicyOptions(BaseModel):
    roles: list[dict]
    departments: list[dict]
    users: list[dict]


class IngestionStatusResponse(BaseModel):
    running: bool
    queue_depth: int
    active_job: dict | None
    last_error: str | None
    last_finished_at: float | None
