import json
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..admin_consistency import audit_admin_action, utc_iso
from ..auth import get_admin_user
from ..models import AdminAuditLog, User, get_db


router = APIRouter(prefix="/api/admin", tags=["admin"])


class RoleUpdate(BaseModel):
    role: Literal["admin", "user"]


def _user_payload(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "created_at": utc_iso(user.created_at),
    }


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    return [_user_payload(user) for user in db.query(User).order_by(User.id).all()]


@router.patch("/users/{user_id}/role")
def update_user_role(
    user_id: int,
    data: RoleUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target.id == admin.id and data.role != "admin":
        raise HTTPException(status_code=409, detail="管理员不能降级自己的账号")
    if target.role == data.role:
        return _user_payload(target)
    before = _user_payload(target)
    if target.role == "admin" and data.role != "admin":
        admin_count = db.query(func.count(User.id)).filter(
            User.role == "admin",
        ).scalar_subquery()
        updated = db.query(User).filter(
            User.id == target.id,
            User.role == "admin",
            admin_count > 1,
        ).update({"role": "user"}, synchronize_session=False)
        if updated != 1:
            db.rollback()
            raise HTTPException(status_code=409, detail="必须至少保留一名管理员")
        db.expire_all()
        target = db.query(User).filter(User.id == user_id).first()
    else:
        target.role = data.role
        db.flush()
    after = _user_payload(target)
    audit_admin_action(
        db,
        request,
        admin,
        action="admin.role.update",
        target_type="user",
        target_id=target.id,
        before=before,
        after=after,
    )
    db.commit()
    return after


@router.get("/audit-logs")
def list_audit_logs(
    limit: int = 100,
    before_id: Optional[int] = None,
    action: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    query = db.query(AdminAuditLog)
    if before_id is not None:
        query = query.filter(AdminAuditLog.id < before_id)
    if action:
        query = query.filter(AdminAuditLog.action == action)
    rows = query.order_by(AdminAuditLog.id.desc()).limit(min(max(limit, 1), 500)).all()

    def parse(value):
        if not value:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None

    return {
        "items": [
            {
                "id": row.id,
                "actor_user_id": row.actor_user_id,
                "actor_username": row.actor_username,
                "action": row.action,
                "target_type": row.target_type,
                "target_id": row.target_id,
                "before": parse(row.before_json),
                "after": parse(row.after_json),
                "request_id": row.request_id,
                "ip_address": row.ip_address,
                "user_agent": row.user_agent,
                "created_at": utc_iso(row.created_at),
            }
            for row in rows
        ],
        "next_before_id": rows[-1].id if len(rows) == min(max(limit, 1), 500) else None,
    }
