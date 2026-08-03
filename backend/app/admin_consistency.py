import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from .clock import utc_now
from .models import AdminAuditLog, SystemState, User


SENSITIVE_KEYS = {
    "api_key",
    "api_key_encrypted",
    "password",
    "password_hash",
    "token",
    "access_token",
}


class RevisionConflict(Exception):
    def __init__(self, current: dict):
        self.current = current


class MaintenanceLocked(Exception):
    def __init__(self, reason: Optional[str] = None):
        self.reason = reason or "系统正在恢复备份，请稍后再试"


def utc_iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or str(uuid.uuid4())


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: ("[redacted]" if key.lower() in SENSITIVE_KEYS else _redact(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, datetime):
        return utc_iso(value)
    return value


def audit_admin_action(
    db: Session,
    request: Request,
    actor: User,
    *,
    action: str,
    target_type: str,
    target_id: Any = None,
    before: Optional[dict] = None,
    after: Optional[dict] = None,
) -> AdminAuditLog:
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    log = AdminAuditLog(
        actor_user_id=actor.id,
        actor_username=actor.username,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        before_json=json.dumps(_redact(before), ensure_ascii=False) if before is not None else None,
        after_json=json.dumps(_redact(after), ensure_ascii=False) if after is not None else None,
        request_id=request_id(request),
        ip_address=forwarded or (request.client.host if request.client else None),
        user_agent=request.headers.get("user-agent"),
        created_at=utc_now(),
    )
    db.add(log)
    return log


def get_system_state(db: Session) -> SystemState:
    state = db.query(SystemState).filter(SystemState.id == 1).first()
    if state is None:
        state = SystemState(id=1)
        db.add(state)
        db.flush()
    return state


def public_system_state(state: SystemState) -> dict:
    return {
        "maintenance_mode": bool(state.maintenance_mode),
        "maintenance_reason": state.maintenance_reason,
        "maintenance_started_at": utc_iso(state.maintenance_started_at),
    }
