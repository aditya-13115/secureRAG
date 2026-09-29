from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api import documents as documents_api
from app.db.database import get_db
from app.db.models import Base, Department, Role, User
from app.ingestion import file_registry


class DummyIngestionManager:
    def __init__(self) -> None:
        self.jobs: list[tuple[str, int]] = []

    def enqueue_index(self, document_id: int) -> bool:
        self.jobs.append(("INDEX", document_id))
        return True

    def enqueue_delete(self, document_id: int) -> bool:
        self.jobs.append(("DELETE", document_id))
        return True

    def snapshot(self) -> dict[str, object]:
        return {
            "running": True,
            "queue_depth": len(self.jobs),
            "active_job": None,
            "last_error": None,
            "last_finished_at": None,
        }


@pytest.fixture
def admin_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    database_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )

    db = Session()

    general = Department(
        code="GENERAL",
        name="General",
    )
    hr = Department(
        code="HR",
        name="Human Resources",
    )
    technology = Department(
        code="TECH",
        name="Technology",
    )

    ceo_role = Role(
        code="CEO",
        name="CEO",
        is_global_access=True,
    )
    engineer_role = Role(
        code="ENGINEER",
        name="Engineer",
        is_global_access=False,
    )

    db.add_all(
        [
            general,
            hr,
            technology,
            ceo_role,
            engineer_role,
        ]
    )
    db.flush()

    admin = User(
        employee_code="ME-CEO",
        email="ceo@monke.ai",
        full_name="CEO User",
        role=ceo_role,
        department=general,
        is_active=True,
    )
    engineer = User(
        employee_code="ME-ENG",
        email="engineer@monke.ai",
        full_name="Engineer User",
        role=engineer_role,
        department=technology,
        is_active=True,
    )

    db.add_all([admin, engineer])
    db.flush()
    admin_role_id = ceo_role.id
    db.commit()
    db.close()

    document_root = tmp_path / "documents"
    document_root.mkdir(parents=True)

    monkeypatch.setattr(
        documents_api,
        "DOCUMENT_ROOT",
        document_root.resolve(),
    )
    monkeypatch.setattr(
        file_registry,
        "DOCUMENT_ROOT",
        document_root.resolve(),
    )

    manager = DummyIngestionManager()
    monkeypatch.setattr(
        documents_api,
        "get_ingestion_manager",
        lambda: manager,
    )

    app = FastAPI()
    app.include_router(documents_api.router)

    def override_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db

    return app, manager, admin_role_id


def test_admin_upload_policy_audit_and_delete(admin_app):
    app, manager, admin_role_id = admin_app
    client = TestClient(app)

    non_admin = {
        "X-User-Email": "engineer@monke.ai",
    }
    admin = {
        "X-User-Email": "ceo@monke.ai",
    }

    assert client.get(
        "/api/documents",
        headers=non_admin,
    ).status_code == 403

    upload = client.post(
        "/api/documents/upload",
        headers=admin,
        data={"category": "hr"},
        files={
            "file": (
                "compensation_test.txt",
                b"Synthetic compensation test document",
                "text/plain",
            )
        },
    )

    assert upload.status_code == 201, upload.text

    detail = upload.json()["document"]
    document_id = detail["id"]

    assert detail["status"] == "PENDING_POLICY"
    assert detail["created_by"]["email"] == "ceo@monke.ai"
    assert any(
        log["action"] == "REGISTERED"
        for log in detail["audit_logs"]
    )

    policy = {
        "classification": "CONFIDENTIAL",
        "access_scope": "ROLE",
        "department_ids": [],
        "role_ids": [admin_role_id],
        "user_ids": [],
    }

    denied_policy = client.patch(
        f"/api/documents/{document_id}/policy",
        headers=non_admin,
        json=policy,
    )
    assert denied_policy.status_code == 403

    approved = client.patch(
        f"/api/documents/{document_id}/policy",
        headers=admin,
        json=policy,
    )
    assert approved.status_code == 200, approved.text

    detail = approved.json()
    assert detail["status"] == "READY_FOR_INGESTION"
    assert detail["policy_updated_by"]["email"] == "ceo@monke.ai"
    assert any(
        log["action"] == "POLICY_UPDATED"
        for log in detail["audit_logs"]
    )
    assert ("INDEX", document_id) in manager.jobs

    deleted = client.delete(
        f"/api/documents/{document_id}",
        headers=admin,
    )
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["status"] == "DELETED"
    assert deleted.json()["file_removed"] is True
    assert ("DELETE", document_id) in manager.jobs

    final_detail = client.get(
        f"/api/documents/{document_id}",
        headers=admin,
    )
    assert final_detail.status_code == 200
    final_data = final_detail.json()
    assert final_data["status"] == "DELETED"
    assert final_data["filesystem"]["exists"] is False
    assert any(
        log["action"] == "DELETE_REQUESTED"
        for log in final_data["audit_logs"]
    )

    # The SQL document remains for audit/history, but it is logically revoked.
