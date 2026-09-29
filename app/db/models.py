from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    Column,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ============================================================
# BASE
# ============================================================


class Base(DeclarativeBase):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================
# ASSOCIATION TABLES
# ============================================================


role_department_access = Table(
    "role_department_access",
    Base.metadata,
    Column(
        "role_id",
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "department_id",
        ForeignKey("departments.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


document_department_access = Table(
    "document_department_access",
    Base.metadata,
    Column(
        "document_id",
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "department_id",
        ForeignKey("departments.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


document_role_access = Table(
    "document_role_access",
    Base.metadata,
    Column(
        "document_id",
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "role_id",
        ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


document_user_access = Table(
    "document_user_access",
    Base.metadata,
    Column(
        "document_id",
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "user_id",
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


# ============================================================
# ROLE
# ============================================================


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # CEO / CTO / COFOUNDER
    is_global_access: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    users: Mapped[List["User"]] = relationship(
        back_populates="role",
    )

    accessible_departments: Mapped[List["Department"]] = relationship(
        secondary=role_department_access,
        back_populates="access_roles",
    )

    accessible_documents: Mapped[List["Document"]] = relationship(
        secondary=document_role_access,
        back_populates="allowed_roles",
    )


# ============================================================
# DEPARTMENT
# ============================================================


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    users: Mapped[List["User"]] = relationship(
        back_populates="department",
    )

    access_roles: Mapped[List["Role"]] = relationship(
        secondary=role_department_access,
        back_populates="accessible_departments",
    )

    owned_documents: Mapped[List["Document"]] = relationship(
        back_populates="owner_department",
    )

    accessible_documents: Mapped[List["Document"]] = relationship(
        secondary=document_department_access,
        back_populates="allowed_departments",
    )


# ============================================================
# USER
# ============================================================


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    employee_code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id"),
        nullable=False,
    )

    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id"),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    role: Mapped["Role"] = relationship(
        back_populates="users",
    )

    department: Mapped["Department"] = relationship(
        back_populates="users",
    )

    explicitly_accessible_documents: Mapped[List["Document"]] = relationship(
        secondary=document_user_access,
        back_populates="allowed_users",
    )


# ============================================================
# AUDIT LOG
# ============================================================


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    action: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    details_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    document: Mapped["Document | None"] = relationship(
        back_populates="audit_logs",
    )

    actor_user: Mapped["User | None"] = relationship()


# ============================================================
# DOCUMENT
# ============================================================


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # Stable application-level document identifier.
    document_key: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
    )

    filename: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
    )

    # Relative path from data/documents/
    relative_path: Mapped[str] = mapped_column(
        String(1000),
        unique=True,
        nullable=False,
        index=True,
    )

    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    owner_department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id"),
        nullable=False,
    )

    classification: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="INTERNAL",
    )

    # PENDING until an admin explicitly assigns a policy.
    # Final values:
    # PUBLIC / DEPARTMENT / ROLE / USER
    access_scope: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="PENDING",
        index=True,
    )

    checksum: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # PENDING_POLICY / READY_FOR_INGESTION
    # INDEXING / INDEXED / FAILED / DELETED
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="PENDING_POLICY",
        index=True,
    )

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    policy_updated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    policy_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    deleted_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True,
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    indexed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    owner_department: Mapped["Department"] = relationship(
        back_populates="owned_documents",
    )

    allowed_departments: Mapped[List["Department"]] = relationship(
        secondary=document_department_access,
        back_populates="accessible_documents",
    )

    allowed_roles: Mapped[List["Role"]] = relationship(
        secondary=document_role_access,
        back_populates="accessible_documents",
    )

    allowed_users: Mapped[List["User"]] = relationship(
        secondary=document_user_access,
        back_populates="explicitly_accessible_documents",
    )

    created_by_user: Mapped["User | None"] = relationship(
        foreign_keys=[created_by_user_id],
    )

    policy_updated_by_user: Mapped["User | None"] = relationship(
        foreign_keys=[policy_updated_by_user_id],
    )

    deleted_by_user: Mapped["User | None"] = relationship(
        foreign_keys=[deleted_by_user_id],
    )

    audit_logs: Mapped[List["AuditLog"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "filename",
            "relative_path",
            name="uq_document_filename_path",
        ),
    )