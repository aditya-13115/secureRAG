from __future__ import annotations

import json
from typing import Any

from app.db.models import AuditLog


def record_audit(
    session,
    *,
    action: str,
    actor_user_id: int | None = None,
    document_id: int | None = None,
    details: dict[str, Any] | None = None,
) -> AuditLog:
    log = AuditLog(
        action=action,
        actor_user_id=actor_user_id,
        document_id=document_id,
        details_json=(
            json.dumps(
                details or {},
                ensure_ascii=False,
                sort_keys=True,
            )
        ),
    )
    session.add(log)
    session.flush()
    return log


def parse_audit_details(value: str | None) -> dict[str, Any]:
    if not value:
        return {}

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {"raw": value}

    return parsed if isinstance(parsed, dict) else {"value": parsed}
