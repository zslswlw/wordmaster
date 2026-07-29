from datetime import datetime

from app.auth import create_access_token
from app.models import ReviewPlan, StudyGroup, StudyRecord, User


def load_scenario(api, name):
    response = api["client"].post(
        f"/api/test/scenarios/{name}",
        headers=api["headers"],
    )
    assert response.status_code == 200, response.text
    return response.json()


def start(api, group_id, *, review=False, enhance=False, plan_id=None):
    query = f"is_review={str(review).lower()}&is_enhance={str(enhance).lower()}"
    if plan_id:
        query += f"&plan_id={plan_id}"
    return api["client"].post(
        f"/api/study/start/{group_id}?{query}",
        headers=api["headers"],
    )


def answer(api, group_id, word_id, word, round_number, study_type, plan_id=None):
    payload = {
        "group_id": group_id,
        "word_id": word_id,
        "user_input": word,
        "round": round_number,
        "study_type": study_type,
    }
    if plan_id:
        payload["plan_id"] = plan_id
    return api["client"].post("/api/study/check", json=payload, headers=api["headers"])


def complete(api, group_id, study_type, plan_id=None):
    query = f"is_enhance={str(study_type == 'enhance').lower()}&study_type={study_type}"
    if plan_id:
        query += f"&plan_id={plan_id}"
    return api["client"].post(
        f"/api/study/complete/{group_id}?{query}",
        headers=api["headers"],
    )


def words_by_id(api, word_ids):
    result = {}
    for word_id in word_ids:
        response = api["client"].get(
            f"/api/study/word/{word_id}",
            headers=api["headers"],
        )
        assert response.status_code == 200
        result[word_id] = response.json()["word"]
    return result


def test_full_lifecycle_is_idempotent(api):
    scenario = load_scenario(api, "fresh")
    group_id = scenario["group_id"]
    first = start(api, group_id)
    assert first.status_code == 200
    first_data = first.json()
    assert first_data["current_round"] == 1
    assert len(first_data["word_ids"]) == 3
    word_map = words_by_id(api, first_data["word_ids"])

    wrong_id = first_data["word_ids"][0]
    for word_id in first_data["word_ids"]:
        submitted = answer(
            api,
            group_id,
            word_id,
            "wrong" if word_id == wrong_id else word_map[word_id],
            1,
            "new",
        )
        assert submitted.status_code == 200

    duplicate = answer(api, group_id, wrong_id, word_map[wrong_id], 1, "new")
    assert duplicate.status_code == 200
    assert duplicate.json()["correct"] is False

    first_complete = complete(api, group_id, "new")
    assert first_complete.json()["next_step"] == "continue"

    second = start(api, group_id)
    assert second.json()["word_ids"] == [wrong_id]
    assert second.json()["current_round"] == 2
    assert answer(api, group_id, wrong_id, word_map[wrong_id], 2, "new").status_code == 200
    assert complete(api, group_id, "new").json()["next_step"] == "enhance"

    enhance = start(api, group_id, enhance=True)
    enhance_words = words_by_id(api, enhance.json()["word_ids"])
    for word_id in enhance.json()["word_ids"]:
        assert answer(
            api,
            group_id,
            word_id,
            enhance_words[word_id],
            enhance.json()["current_round"],
            "enhance",
        ).status_code == 200

    assert complete(api, group_id, "enhance").json()["next_step"] == "completed"
    assert complete(api, group_id, "enhance").json()["next_step"] == "completed"

    db = api["session"]()
    try:
        assert db.query(StudyRecord).filter(
            StudyRecord.group_id == group_id,
            StudyRecord.word_id == wrong_id,
            StudyRecord.round == 1,
            StudyRecord.study_type == "new",
        ).count() == 1
        assert db.query(ReviewPlan).filter(ReviewPlan.group_id == group_id).count() == 5
        plans = db.query(ReviewPlan).filter(
            ReviewPlan.group_id == group_id
        ).order_by(ReviewPlan.review_round).all()
        assert [plan.review_date.isoformat() for plan in plans] == [
            "2026-07-30",
            "2026-08-01",
            "2026-08-05",
            "2026-08-13",
            "2026-08-28",
        ]
    finally:
        db.close()


def test_incomplete_round_cannot_be_completed(api):
    scenario = load_scenario(api, "fresh")
    group_id = scenario["group_id"]
    session = start(api, group_id).json()
    word_id = session["word_ids"][0]
    word = words_by_id(api, [word_id])[word_id]
    assert answer(api, group_id, word_id, word, 1, "new").status_code == 200

    result = complete(api, group_id, "new").json()
    assert result["next_step"] == "continue"
    assert result["remaining_count"] == 2

    db = api["session"]()
    try:
        assert db.query(StudyGroup).filter(StudyGroup.id == group_id).one().status == "learning"
        assert db.query(ReviewPlan).filter(ReviewPlan.group_id == group_id).count() == 0
    finally:
        db.close()


def test_partial_round_resumes_with_only_unanswered_word(api):
    scenario = load_scenario(api, "partial-round")
    response = start(api, scenario["group_id"])
    assert response.status_code == 200
    assert len(response.json()["word_ids"]) == 1
    assert response.json()["word_ids"][0] == scenario["word_ids"][2]


def test_fake_clock_crosses_midnight_without_waiting(api):
    api["clock"].set(datetime.fromisoformat("2026-07-29T23:59:00+08:00"))
    load_scenario(api, "completed-day0")

    before = api["client"].get("/api/review/today", headers=api["headers"])
    assert before.json() == []

    advanced = api["client"].post(
        "/api/test/clock/advance",
        json={"days": 0, "minutes": 2},
        headers=api["headers"],
    )
    assert advanced.json()["business_date"] == "2026-07-30"

    after = api["client"].get("/api/review/today", headers=api["headers"]).json()
    assert len(after) == 1
    assert after[0]["review_round"] == 1
    assert after[0]["can_review"] is True


def test_overdue_reviews_preserve_dates_and_unlock_in_order(api):
    scenario = load_scenario(api, "overdue-backlog")
    group_id = scenario["group_id"]
    due = api["client"].get("/api/review/today", headers=api["headers"]).json()
    assert [plan["review_round"] for plan in due] == [1, 2, 3, 4]
    assert [plan["can_review"] for plan in due] == [True, False, False, False]
    original_dates = [plan["review_date"] for plan in due]

    blocked = start(api, group_id, review=True, plan_id=due[1]["plan_id"])
    assert blocked.status_code == 409

    first = api["client"].post(
        f"/api/review/start/{due[0]['plan_id']}",
        headers=api["headers"],
    )
    assert len(first.json()["word_ids"]) == 3
    word_map = words_by_id(api, first.json()["word_ids"])
    for word_id in first.json()["word_ids"]:
        response = answer(
            api,
            group_id,
            word_id,
            word_map[word_id],
            1,
            "review",
            due[0]["plan_id"],
        )
        assert response.status_code == 200
    compatibility_complete = api["client"].post(
        f"/api/review/complete/{due[0]['plan_id']}",
        headers=api["headers"],
    )
    assert compatibility_complete.json()["next_step"] == "completed"

    updated = api["client"].get("/api/review/today", headers=api["headers"]).json()
    assert [plan["review_date"] for plan in updated] == original_dates[1:]
    assert updated[0]["review_round"] == 2
    assert updated[0]["can_review"] is True


def test_future_review_and_forged_round_are_rejected(api):
    scenario = load_scenario(api, "completed-day0")
    plans = api["client"].get("/api/review/all", headers=api["headers"]).json()
    future = start(api, scenario["group_id"], review=True, plan_id=plans[0]["plan_id"])
    assert future.status_code == 400
    future_answer = answer(
        api,
        scenario["group_id"],
        scenario["word_ids"][0],
        "apple",
        1,
        "review",
        plans[0]["plan_id"],
    )
    assert future_answer.status_code == 400

    fresh = load_scenario(api, "fresh")
    bad_round = answer(
        api,
        fresh["group_id"],
        fresh["word_ids"][0],
        "apple",
        2,
        "new",
    )
    assert bad_round.status_code == 409

    early_enhance = answer(
        api,
        fresh["group_id"],
        fresh["word_ids"][0],
        "apple",
        1,
        "enhance",
    )
    assert early_enhance.status_code == 409


def test_completed_today_uses_business_timezone(api):
    api["clock"].set(datetime.fromisoformat("2026-07-30T00:30:00+08:00"))
    scenario = load_scenario(api, "completed-day0")
    db = api["session"]()
    try:
        plan = db.query(ReviewPlan).filter(
            ReviewPlan.group_id == scenario["group_id"],
            ReviewPlan.review_round == 1,
        ).one()
        plan.review_date = api["clock"].today()
        plan.original_date = plan.review_date
        db.commit()
        plan_id = plan.id
    finally:
        db.close()

    session = start(api, scenario["group_id"], review=True, plan_id=plan_id).json()
    word_map = words_by_id(api, session["word_ids"])
    for word_id in session["word_ids"]:
        assert answer(
            api,
            scenario["group_id"],
            word_id,
            word_map[word_id],
            1,
            "review",
            plan_id,
        ).status_code == 200
    assert complete(
        api,
        scenario["group_id"],
        "review",
        plan_id,
    ).json()["next_step"] == "completed"

    groups = api["client"].get("/api/groups", headers=api["headers"]).json()
    assert groups[0]["today_review_status"] == "completed"


def test_other_user_cannot_access_group(api):
    scenario = load_scenario(api, "fresh")
    db = api["session"]()
    try:
        other = User(
            username="other",
            password_hash="unused",
            role="user",
            created_at=api["clock"].utcnow(),
        )
        db.add(other)
        db.commit()
        db.refresh(other)
        token = create_access_token({"sub": other.username, "role": other.role})
    finally:
        db.close()

    response = api["client"].post(
        f"/api/study/start/{scenario['group_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_ten_word_review_stays_pending_until_all_ten_are_answered(api):
    scenario = load_scenario(api, "ten-word-review")
    group_id = scenario["group_id"]
    plans = api["client"].get("/api/review/today", headers=api["headers"]).json()
    assert len(plans) == 1
    plan_id = plans[0]["plan_id"]

    review = start(api, group_id, review=True, plan_id=plan_id)
    assert review.status_code == 200
    word_ids = review.json()["word_ids"]
    assert len(word_ids) == 10
    word_map = words_by_id(api, word_ids)

    for word_id in word_ids[:6]:
        submitted = answer(
            api,
            group_id,
            word_id,
            word_map[word_id],
            1,
            "review",
            plan_id,
        )
        assert submitted.status_code == 200

    stats = api["client"].get(
        f"/api/study/round/{group_id}?study_type=review&current_round=1&plan_id={plan_id}",
        headers=api["headers"],
    ).json()["current_round_stats"]
    assert stats == {
        "correct": 6,
        "wrong": 0,
        "total": 6,
        "expected": 10,
        "remaining": 4,
    }

    premature_complete = complete(api, group_id, "review", plan_id).json()
    assert premature_complete["next_step"] == "continue"
    assert premature_complete["remaining_count"] == 4

    pending = api["client"].get("/api/review/today", headers=api["headers"]).json()
    assert len(pending) == 1
    assert pending[0]["status"] == "pending"
    assert pending[0]["can_review"] is True

    groups = api["client"].get("/api/groups", headers=api["headers"]).json()
    assert groups[0]["today_review_status"] == "pending"

    resumed = start(api, group_id, review=True, plan_id=plan_id).json()
    assert set(resumed["word_ids"]) == set(word_ids[6:])
    assert resumed["is_completed"] is False
