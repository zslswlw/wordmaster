from app import models
from app.auth import create_access_token
from app.main import app
from fastapi.testclient import TestClient


def _add_user(api, username: str, role: str):
    session = api["session"]()
    user = models.User(
        username=username,
        password_hash="not-used",
        role=role,
        created_at=api["clock"].utcnow(),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    user_id = user.id
    session.close()
    token = create_access_token({"sub": username, "role": role})
    return user_id, {"Authorization": f"Bearer {token}"}


def _flags_payload(revision: int, **overrides):
    values = {
        "example_enabled": True,
        "image_enabled": True,
        "mnemonic_enabled": True,
        "error_analysis_enabled": True,
        "story_enabled": False,
        "expected_revision": revision,
    }
    values.update(overrides)
    return values


def test_stale_feature_flag_write_is_rejected_and_audited(api):
    _, admin_b = _add_user(api, "admin-b", "admin")
    first = api["client"].get(
        "/api/settings/feature-flags",
        headers=api["headers"],
    ).json()
    stale_revision = first["revision"]

    saved = api["client"].put(
        "/api/settings/feature-flags",
        headers=api["headers"],
        json=_flags_payload(stale_revision, image_enabled=False),
    )
    assert saved.status_code == 200

    with TestClient(app) as browser_b:
        stale = browser_b.put(
            "/api/settings/feature-flags",
            headers=admin_b,
            json=_flags_payload(stale_revision, story_enabled=True),
        )
    assert stale.status_code == 409
    assert stale.json()["code"] == "stale_revision"
    assert stale.json()["current"]["image_enabled"] is False

    retried = api["client"].put(
        "/api/settings/feature-flags",
        headers=admin_b,
        json=_flags_payload(
            stale.json()["current"]["revision"],
            image_enabled=False,
            story_enabled=True,
        ),
    )
    assert retried.status_code == 200
    assert retried.json()["image_enabled"] is False
    assert retried.json()["story_enabled"] is True

    audit = api["client"].get(
        "/api/admin/audit-logs",
        headers=api["headers"],
    ).json()["items"]
    actors = [row["actor_username"] for row in audit if row["action"] == "feature_flags.update"]
    assert actors == ["admin-b", "tester"]


def test_worker_patch_preserves_other_fields_and_same_pause_is_idempotent(api):
    _, admin_b = _add_user(api, "admin-b", "admin")
    worker = api["client"].get(
        "/api/ai/evolution/worker",
        headers=api["headers"],
    ).json()

    first = api["client"].patch(
        "/api/ai/evolution/worker",
        headers=api["headers"],
        json={"expected_revision": worker["revision"], "quota_reserve_percent": 40},
    )
    assert first.status_code == 200
    stale = api["client"].patch(
        "/api/ai/evolution/worker",
        headers=admin_b,
        json={"expected_revision": worker["revision"], "feedback_reserve_percent": 25},
    )
    assert stale.status_code == 409
    current = stale.json()["current"]
    retry = api["client"].patch(
        "/api/ai/evolution/worker",
        headers=admin_b,
        json={"expected_revision": current["revision"], "feedback_reserve_percent": 25},
    )
    assert retry.status_code == 200
    assert retry.json()["quota_reserve_percent"] == 40
    assert retry.json()["feedback_reserve_percent"] == 25

    revision = retry.json()["revision"]
    pause_a = api["client"].patch(
        "/api/ai/evolution/worker",
        headers=api["headers"],
        json={"expected_revision": revision, "paused": True},
    )
    pause_b = api["client"].patch(
        "/api/ai/evolution/worker",
        headers=admin_b,
        json={"expected_revision": revision, "paused": True},
    )
    assert pause_a.status_code == pause_b.status_code == 200
    assert pause_b.json()["revision"] == pause_a.json()["revision"]

    audit = api["client"].get(
        "/api/admin/audit-logs",
        headers=api["headers"],
    ).json()["items"]
    pause_actors = [row["actor_username"] for row in audit if row["action"] == "ai_worker.pause"]
    assert pause_actors == ["admin-b", "tester"]


def test_server_role_check_ignores_forged_token_claim_and_protects_admins(api):
    user_id, _ = _add_user(api, "ordinary", "user")
    forged = create_access_token({"sub": "ordinary", "role": "admin"})
    forged_headers = {"Authorization": f"Bearer {forged}"}
    denied = api["client"].get("/api/admin/users", headers=forged_headers)
    assert denied.status_code == 403

    admin_b_id, _ = _add_user(api, "admin-b", "admin")
    users = api["client"].get("/api/admin/users", headers=api["headers"]).json()
    current_id = next(row["id"] for row in users if row["username"] == "tester")
    self_demote = api["client"].patch(
        f"/api/admin/users/{current_id}/role",
        headers=api["headers"],
        json={"role": "user"},
    )
    assert self_demote.status_code == 409

    promoted = api["client"].patch(
        f"/api/admin/users/{user_id}/role",
        headers=api["headers"],
        json={"role": "admin"},
    )
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "admin"
    demoted = api["client"].patch(
        f"/api/admin/users/{admin_b_id}/role",
        headers=api["headers"],
        json={"role": "user"},
    )
    assert demoted.status_code == 200
    assert demoted.json()["role"] == "user"


def test_maintenance_blocks_writes_but_keeps_read_dashboard_and_utc_times(api):
    worker = api["client"].get(
        "/api/ai/evolution/worker",
        headers=api["headers"],
    ).json()
    session = api["session"]()
    state = models.SystemState(
        id=1,
        maintenance_mode=True,
        maintenance_reason="测试恢复",
        maintenance_started_by=api["user_id"],
        maintenance_started_at=api["clock"].utcnow(),
    )
    session.add(state)
    session.commit()
    session.close()

    blocked = api["client"].patch(
        "/api/ai/evolution/worker",
        headers=api["headers"],
        json={"expected_revision": worker["revision"], "paused": True},
    )
    assert blocked.status_code == 423
    assert blocked.json()["code"] == "maintenance_locked"

    dashboard = api["client"].get(
        "/api/ai/evolution/dashboard",
        headers=api["headers"],
    )
    assert dashboard.status_code == 200
    assert dashboard.json()["observed_at"].endswith("Z")


def test_audit_redacts_api_keys(api):
    created = api["client"].post(
        "/api/settings/ai-configs",
        headers=api["headers"],
        json={
            "provider": "minimax",
            "api_key": "top-secret-value",
            "api_base": "https://api.minimaxi.com",
            "text_model": "MiniMax-M3",
        },
    )
    assert created.status_code == 200
    audit = api["client"].get(
        "/api/admin/audit-logs",
        headers=api["headers"],
    ).text
    assert "top-secret-value" not in audit
    assert "api_key_encrypted" not in audit
