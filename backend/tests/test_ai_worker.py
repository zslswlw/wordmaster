import asyncio
import threading
import time
from datetime import timedelta, timezone
from types import SimpleNamespace

import pytest

from app import models
from app.clock import utc_now
from app.services.ai import MemoryBundleCandidate, MemoryQualityScores
from app.services.ai.base import ConfigurationError
from app.services.ai.worker import (
    MEDIA_JOB_KINDS,
    TEXT_JOB_KINDS,
    AiJobProcessor,
    _extract_quota_state,
)
from app.services.learning_content import (
    LearningContentResolver,
    queue_ai_job,
    seed_word_evolution,
)


class FakeMiniMax:
    config = SimpleNamespace(
        text_model="MiniMax-M3",
        image_model="image-01",
        speech_model="speech-2.8-turbo",
    )

    async def get_quota(self):
        return {"remaining_percent": 80}

    async def generate_image(self, prompt):
        return b"\x89PNG\r\n\x1a\n" + (b"image" * 40)

    async def text_to_speech(self, text):
        return b"ID3" + (b"audio" * 40)


class FakeAiService:
    def __init__(self, db):
        self.db = db
        self.minimax = FakeMiniMax()
        self.text_provider = self.minimax

    async def generate_memory_candidate(
        self,
        word,
        feedback_context="",
        validation_feedback="",
    ):
        suffix = "新版" if feedback_context else "初版"
        return MemoryBundleCandidate(
            normalized_pos="名词",
            primary_meaning="港口",
            strategy="direct",
            memory_anchor=f"{suffix}：一艘船驶入港口，红色浮标标出入口",
            scene_summary="船驶入港口",
            image_prompt=f"One ship enters a harbor beside one red buoy, {'revised scene' if feedback_context else 'clear scene'}, no text or letters.",
            narration_text="名词，港口",
            scores=MemoryQualityScores(
                meaning_consistency=5,
                association_naturalness=5,
                visual_clarity=5,
                distinctiveness=4,
            ),
            approved=True,
        )


class SlowAiService(FakeAiService):
    started = threading.Event()

    async def generate_memory_candidate(self, word, feedback_context=""):
        self.started.set()
        await asyncio.sleep(0.2)
        return await super().generate_memory_candidate(word, feedback_context)


class SlowMiniMax(FakeMiniMax):
    async def generate_image(self, prompt):
        await asyncio.sleep(0.2)
        return await super().generate_image(prompt)


class DualLaneSlowAiService(FakeAiService):
    def __init__(self, db):
        super().__init__(db)
        self.minimax = SlowMiniMax()

    async def generate_memory_candidate(self, word, feedback_context=""):
        await asyncio.sleep(0.2)
        return await super().generate_memory_candidate(word, feedback_context)


class FatalAiService(FakeAiService):
    async def generate_memory_candidate(self, word, feedback_context=""):
        raise ConfigurationError("MiniMax API Key 无效", code="1004")


class CorrectingAiService(FakeAiService):
    calls = []

    async def generate_memory_candidate(
        self,
        word,
        feedback_context="",
        validation_feedback="",
    ):
        self.calls.append(validation_feedback)
        if not validation_feedback:
            raise ValueError("memory_anchor exceeds 45 Chinese characters")
        return await super().generate_memory_candidate(word, feedback_context)


def _run(coro):
    return asyncio.run(coro)


def test_memory_anchor_limit_counts_chinese_characters_not_punctuation():
    values = {
        "normalized_pos": "名词",
        "primary_meaning": "测试",
        "strategy": "direct",
        "scene_summary": "测试画面",
        "image_prompt": "One clear test object with one red mark, no text or letters.",
        "narration_text": "名词，测试",
        "scores": {
            "meaning_consistency": 5,
            "association_naturalness": 5,
            "visual_clarity": 5,
            "distinctiveness": 5,
        },
        "approved": True,
    }

    candidate = MemoryBundleCandidate(
        **values,
        memory_anchor=("一" * 45) + "，。！",
    )
    assert len(candidate.memory_anchor) == 48
    with pytest.raises(ValueError):
        MemoryBundleCandidate(
            **values,
            memory_anchor="一" * 46,
        )


def test_persistent_worker_builds_assets_and_atomically_replaces_feedback(
    api,
    monkeypatch,
    tmp_path,
):
    from app.services.ai import worker as worker_module

    monkeypatch.setenv("AI_MEDIA_DIR", str(tmp_path / "ai-media"))
    monkeypatch.setattr(worker_module, "AiService", FakeAiService)
    session = api["session"]()
    bank = models.WordBank(name="worker", user_id=api["user_id"], word_count=1)
    session.add(bank)
    session.flush()
    word = models.Word(
        bank_id=bank.id,
        seq_num=1,
        word="harbor",
        phonetic="/hɑːbə/",
        meaning="n. 港口；避风港",
    )
    session.add(word)
    session.flush()
    original_facts = (word.word, word.phonetic, word.meaning)
    seed_word_evolution(session, word, priority=10)
    session.add(models.AiQuotaSnapshot(
        provider="minimax",
        remaining_percent=80,
        status="available",
        checked_at=utc_now(),
    ))
    session.commit()

    processor = AiJobProcessor(session)
    assert _run(processor.process_next())
    assert _run(processor.process_next())
    assert _run(processor.process_next())

    link = session.query(models.WordMemoryLink).filter_by(word_id=word.id).one()
    old_bundle_id = link.active_bundle_id
    content = LearningContentResolver(session).resolve(word)
    assert content["image_status"] == "ready"
    assert content["audio_status"] == "ready"

    feedback = models.MemoryFeedback(
        user_id=api["user_id"],
        word_id=word.id,
        bundle_id=old_bundle_id,
        component="image",
        reason="词义不准",
        status="pending",
    )
    session.add(feedback)
    session.flush()
    queue_ai_job(
        session,
        kind="feedback_bundle",
        target_type="feedback",
        target_id=feedback.id,
        bank_id=bank.id,
        priority=1,
        payload={"feedback_id": feedback.id},
        idempotency_key=f"feedback:{feedback.id}:replacement",
    )
    session.commit()

    assert _run(processor.process_next())
    session.refresh(feedback)
    replacement_id = feedback.replacement_bundle_id
    session.refresh(link)
    assert link.active_bundle_id == old_bundle_id
    assert feedback.status == "generating"

    assert _run(processor.process_next())
    session.refresh(link)
    assert link.active_bundle_id == old_bundle_id

    assert _run(processor.process_next())
    session.refresh(link)
    session.refresh(feedback)
    assert link.active_bundle_id == replacement_id
    assert feedback.status == "resolved"
    assert session.get(models.MemoryBundle, old_bundle_id).status == "archived"
    assert session.get(models.MemoryBundle, replacement_id).status == "active"

    image_feedback = models.MemoryFeedback(
        user_id=api["user_id"],
        word_id=word.id,
        bundle_id=replacement_id,
        component="image",
        reason="图片质量差",
        status="pending",
    )
    session.add(image_feedback)
    session.flush()
    queue_ai_job(
        session,
        kind="feedback_bundle",
        target_type="feedback",
        target_id=image_feedback.id,
        bank_id=bank.id,
        priority=1,
        payload={"feedback_id": image_feedback.id},
        idempotency_key=f"feedback:{image_feedback.id}:replacement",
    )
    session.commit()
    assert _run(processor.process_next())
    session.refresh(image_feedback)
    image_replacement_id = image_feedback.replacement_bundle_id
    queued_kinds = {
        row.kind
        for row in session.query(models.AiJob).filter(
            models.AiJob.target_id == image_replacement_id,
            models.AiJob.status == "pending",
        ).all()
    }
    assert queued_kinds == {"image"}
    session.refresh(link)
    assert link.active_bundle_id == replacement_id
    assert _run(processor.process_next())
    session.refresh(link)
    assert link.active_bundle_id == image_replacement_id

    session.refresh(word)
    assert (word.word, word.phonetic, word.meaning) == original_facts
    session.close()


def test_quota_reserve_stops_normal_job_without_consuming_attempt(api):
    session = api["session"]()
    bank = models.WordBank(name="quota", user_id=api["user_id"], word_count=1)
    session.add(bank)
    session.flush()
    word = models.Word(bank_id=bank.id, seq_num=1, word="plain", phonetic="", meaning="adj. 普通的")
    session.add(word)
    session.flush()
    seed_word_evolution(session, word)
    session.add(models.AiQuotaSnapshot(
        provider="minimax",
        remaining_percent=25,
        status="available",
        checked_at=utc_now(),
    ))
    session.commit()

    processed = _run(AiJobProcessor(session).process_next())
    job = session.query(models.AiJob).filter_by(kind="bundle_text").one()

    assert not processed
    assert job.status == "pending"
    assert job.attempts == 0
    assert job.last_error_code == "quota_reserve"
    session.close()


def test_running_job_recovers_after_restart_and_status_survives_refresh(api):
    session = api["session"]()
    bank = models.WordBank(name="resume", user_id=api["user_id"], word_count=1)
    session.add(bank)
    session.flush()
    word = models.Word(
        bank_id=bank.id,
        seq_num=1,
        word="resume",
        phonetic="",
        meaning="v. 继续",
    )
    session.add(word)
    session.flush()
    seed_word_evolution(session, word)
    session.commit()
    job = session.query(models.AiJob).filter_by(kind="bundle_text").one()
    job.status = "running"
    job.attempts = 1
    session.commit()
    bank_id, job_id = bank.id, job.id
    session.close()

    first = api["client"].get(
        f"/api/ai/evolution/banks/{bank_id}/coverage",
        headers=api["headers"],
    )
    second = api["client"].get(
        f"/api/ai/evolution/banks/{bank_id}/coverage",
        headers=api["headers"],
    )

    assert first.status_code == 200
    assert first.json()["queue"]["state"] == "running"
    assert first.json()["queue"]["current_job"]["id"] == job_id
    assert second.json()["queue"] == first.json()["queue"]

    session = api["session"]()
    processor = AiJobProcessor(session)
    assert processor.recover_interrupted() == 1
    recovered = session.get(models.AiJob, job_id)
    assert recovered.status == "pending"
    assert recovered.attempts == 1
    assert recovered.last_error_message == "应用重启后恢复"
    session.close()

    resumed = api["client"].get(
        f"/api/ai/evolution/banks/{bank_id}/coverage",
        headers=api["headers"],
    )
    worker = api["client"].get(
        "/api/ai/evolution/worker",
        headers=api["headers"],
    )

    assert resumed.json()["queue"]["state"] == "queued"
    assert resumed.json()["queue"]["active_jobs"] == 1
    assert worker.json()["state"] == "stalled"
    assert worker.json()["queue"]["next_job"]["id"] == job_id


def test_quota_parser_understands_production_token_plan_payload():
    payload = {
        "model_remains": [
            {
                "model_name": "general",
                "current_interval_remaining_percent": 74,
                "current_weekly_remaining_percent": 86,
                "end_time": 1785326400000,
                "weekly_end_time": 1785686400000,
            },
            {
                "model_name": "video",
                "current_interval_remaining_percent": 100,
                "current_weekly_remaining_percent": 100,
                "end_time": 1785340800000,
                "weekly_end_time": 1785686400000,
            },
        ],
        "base_resp": {"status_code": 0, "status_msg": "success"},
    }

    remaining, reset_at = _extract_quota_state(payload)

    assert remaining == 74
    assert int(reset_at.replace(tzinfo=timezone.utc).timestamp() * 1000) == 1785326400000


def test_stale_running_job_is_recovered_without_touching_current_job(api):
    session = api["session"]()
    now = utc_now()
    stale = models.AiJob(
        id="stale-job",
        kind="bundle_text",
        target_type="word",
        target_id=1,
        priority=10,
        status="running",
        attempts=1,
        available_at=now,
        idempotency_key="stale-job",
        created_at=now - timedelta(minutes=20),
        updated_at=now - timedelta(minutes=11),
    )
    current = models.AiJob(
        id="current-job",
        kind="bundle_text",
        target_type="word",
        target_id=2,
        priority=10,
        status="running",
        attempts=1,
        available_at=now,
        idempotency_key="current-job",
        created_at=now,
        updated_at=now,
    )
    session.add_all([stale, current])
    session.commit()

    assert AiJobProcessor(session).recover_stale() == 1
    session.refresh(stale)
    session.refresh(current)

    assert stale.status == "pending"
    assert stale.last_error_code == "stale_recovered"
    assert current.status == "running"
    session.close()


def test_dashboard_returns_one_consistent_persistent_snapshot(api, monkeypatch):
    from app.routers import ai_evolution

    now = utc_now()
    monkeypatch.setattr(
        ai_evolution,
        "silent_worker_status",
        lambda: {
            "alive": True,
            "heartbeat_at": now,
            "last_success_at": None,
            "last_error": None,
        },
    )
    session = api["session"]()
    bank = models.WordBank(name="dashboard", user_id=api["user_id"], word_count=1)
    session.add(bank)
    session.flush()
    word = models.Word(
        bank_id=bank.id,
        seq_num=1,
        word="continue",
        phonetic="",
        meaning="v. 继续",
    )
    session.add(word)
    session.flush()
    seed_word_evolution(session, word)
    session.commit()
    bank_id = bank.id
    session.close()

    response = api["client"].get(
        "/api/ai/evolution/dashboard",
        headers=api["headers"],
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["worker"]["state"] == "queued"
    assert payload["jobs"]["pending"] == 1
    assert payload["banks"] == [{
        "id": bank_id,
            "name": "dashboard",
            "word_count": 1,
            "revision": 1,
        "bank_id": bank_id,
        "total": 1,
        "text_ready": 0,
        "visual_ready": 0,
        "complete_ready": 0,
        "text_ready_percent": 0,
        "visual_ready_percent": 0,
        "complete_ready_percent": 0,
        "queue": payload["banks"][0]["queue"],
    }]
    assert payload["banks"][0]["queue"]["active_jobs"] == 1


def test_dashboard_polling_does_not_interrupt_running_worker(api, monkeypatch):
    from app.services.ai import worker as worker_module

    SlowAiService.started.clear()
    monkeypatch.setattr(worker_module, "AiService", SlowAiService)
    session = api["session"]()
    bank = models.WordBank(name="concurrent", user_id=api["user_id"], word_count=1)
    session.add(bank)
    session.flush()
    word = models.Word(
        bank_id=bank.id,
        seq_num=1,
        word="steady",
        phonetic="",
        meaning="adj. 稳定的",
    )
    session.add(word)
    session.flush()
    seed_word_evolution(session, word)
    session.add(models.AiQuotaSnapshot(
        provider="minimax",
        remaining_percent=80,
        status="available",
        checked_at=utc_now(),
    ))
    session.commit()
    job_id = session.query(models.AiJob).filter_by(kind="bundle_text").one().id
    session.close()

    result = {}

    def run_worker():
        worker_session = api["session"]()
        try:
            result["processed"] = _run(AiJobProcessor(worker_session).process_next())
        finally:
            worker_session.close()

    thread = threading.Thread(target=run_worker)
    thread.start()
    assert SlowAiService.started.wait(timeout=1)

    responses = [
        api["client"].get(
            "/api/ai/evolution/dashboard",
            headers=api["headers"],
        )
        for _ in range(5)
    ]
    thread.join(timeout=2)

    assert not thread.is_alive()
    assert all(response.status_code == 200 for response in responses)
    assert any(
        response.json()["worker"]["queue"]["current_job"]["id"] == job_id
        for response in responses
        if response.json()["worker"]["queue"]["current_job"]
    )
    assert result == {"processed": True}

    session = api["session"]()
    job = session.get(models.AiJob, job_id)
    assert job.status == "completed"
    assert job.attempts == 1
    assert session.connection().exec_driver_sql(
        "PRAGMA journal_mode"
    ).scalar().lower() == "wal"
    assert session.connection().exec_driver_sql(
        "PRAGMA busy_timeout"
    ).scalar() == 30000
    session.close()


def test_text_and_media_lanes_can_progress_concurrently(api, monkeypatch, tmp_path):
    from app.services.ai import worker as worker_module

    monkeypatch.setenv("AI_MEDIA_DIR", str(tmp_path / "ai-media"))
    monkeypatch.setattr(worker_module, "AiService", DualLaneSlowAiService)
    session = api["session"]()
    bank = models.WordBank(name="lanes", user_id=api["user_id"], word_count=2)
    session.add(bank)
    session.flush()
    word = models.Word(
        bank_id=bank.id,
        seq_num=1,
        word="parallel",
        phonetic="",
        meaning="adj. 并行的",
    )
    session.add(word)
    session.flush()
    seed_word_evolution(session, word, priority=10)
    bundle = models.MemoryBundle(
        lexeme_key="lane-bundle",
        word_text="picture",
        normalized_pos="名词",
        primary_meaning="图片",
        strategy="direct",
        memory_anchor="一张图片直接表示图片的含义",
        scene_summary="桌上一张图片",
        image_prompt="One printed picture on a plain desk, one red corner, no text.",
        narration_text="名词，图片",
        prompt_version="memory-v1",
        content_version=1,
        status="active",
    )
    session.add(bundle)
    session.flush()
    queue_ai_job(
        session,
        kind="image",
        target_type="bundle",
        target_id=bundle.id,
        bank_id=bank.id,
        priority=10,
        idempotency_key="lane:image",
    )
    session.add(models.AiQuotaSnapshot(
        provider="minimax",
        remaining_percent=80,
        status="available",
        checked_at=utc_now(),
    ))
    session.commit()
    word_id = word.id
    session.close()

    async def run_lanes():
        text_session = api["session"]()
        media_session = api["session"]()
        try:
            return await asyncio.gather(
                AiJobProcessor(text_session).process_next(TEXT_JOB_KINDS),
                AiJobProcessor(media_session).process_next(MEDIA_JOB_KINDS),
            )
        finally:
            text_session.close()
            media_session.close()

    started = time.perf_counter()
    processed = _run(run_lanes())
    elapsed = time.perf_counter() - started

    assert processed == [True, True]
    assert elapsed < 0.38
    session = api["session"]()
    statuses = dict(
        session.query(models.AiJob.kind, models.AiJob.status).filter(
            models.AiJob.idempotency_key.in_((
                f"word:{word_id}:bundle:memory-v1",
                "lane:image",
            )),
        ).all()
    )
    assert statuses == {"bundle_text": "completed", "image": "completed"}
    session.close()


def test_validation_retry_receives_first_error(api, monkeypatch):
    from app.services.ai import worker as worker_module

    CorrectingAiService.calls.clear()
    monkeypatch.setattr(worker_module, "AiService", CorrectingAiService)
    session = api["session"]()
    bank = models.WordBank(name="correction", user_id=api["user_id"], word_count=1)
    session.add(bank)
    session.flush()
    word = models.Word(
        bank_id=bank.id,
        seq_num=1,
        word="correct",
        phonetic="",
        meaning="v. 修正",
    )
    session.add(word)
    session.flush()
    seed_word_evolution(session, word)
    session.add(models.AiQuotaSnapshot(
        provider="minimax",
        remaining_percent=80,
        status="available",
        checked_at=utc_now(),
    ))
    session.commit()

    assert _run(AiJobProcessor(session).process_next(TEXT_JOB_KINDS))
    assert CorrectingAiService.calls == ["", "memory_anchor exceeds 45 Chinese characters"]
    session.close()


def test_only_fatal_configuration_error_pauses_worker_with_reason(api, monkeypatch):
    from app.services.ai import worker as worker_module

    monkeypatch.setattr(worker_module, "AiService", FatalAiService)
    session = api["session"]()
    bank = models.WordBank(name="fatal", user_id=api["user_id"], word_count=1)
    session.add(bank)
    session.flush()
    word = models.Word(
        bank_id=bank.id,
        seq_num=1,
        word="invalid",
        phonetic="",
        meaning="adj. 无效的",
    )
    session.add(word)
    session.flush()
    seed_word_evolution(session, word)
    session.add(models.AiQuotaSnapshot(
        provider="minimax",
        remaining_percent=80,
        status="available",
        checked_at=utc_now(),
    ))
    session.commit()

    assert not _run(AiJobProcessor(session).process_next(TEXT_JOB_KINDS))
    flags = session.query(models.FeatureFlags).first()
    job = session.query(models.AiJob).filter_by(kind="bundle_text").one()
    assert flags.ai_worker_paused is True
    assert flags.ai_worker_pause_reason == "MiniMax API Key 无效"
    assert flags.ai_worker_paused_at is not None
    assert job.status == "failed"
    assert job.last_error_code == "1004"
    session.close()


def test_resume_requeues_recoverable_failures_but_not_content_rejections(api):
    session = api["session"]()
    now = utc_now()
    recoverable = models.AiJob(
        id="recoverable",
        kind="bundle_text",
        target_type="word",
        target_id=1,
        priority=10,
        status="failed",
        attempts=1,
        available_at=now,
        idempotency_key="recoverable",
        last_error_code="content_validation",
    )
    rejected = models.AiJob(
        id="rejected",
        kind="image",
        target_type="bundle",
        target_id=1,
        priority=10,
        status="failed",
        attempts=1,
        available_at=now,
        idempotency_key="rejected",
        last_error_code="1027",
    )
    flags = session.query(models.FeatureFlags).first()
    if not flags:
        flags = models.FeatureFlags(id=1)
        session.add(flags)
    flags.ai_worker_paused = True
    flags.ai_worker_pause_reason = "旧错误"
    flags.ai_worker_paused_at = now
    session.add_all([recoverable, rejected])
    session.commit()
    session.close()

    current = api["client"].get(
        "/api/ai/evolution/worker",
        headers=api["headers"],
    ).json()
    response = api["client"].put(
        "/api/ai/evolution/worker",
        headers=api["headers"],
        json={"paused": False, "expected_revision": current["revision"]},
    )

    assert response.status_code == 200
    assert response.json()["requeued_failed"] == 1
    session = api["session"]()
    recoverable = session.get(models.AiJob, "recoverable")
    rejected = session.get(models.AiJob, "rejected")
    flags = session.query(models.FeatureFlags).first()
    assert recoverable.status == "pending"
    assert recoverable.attempts == 0
    assert rejected.status == "failed"
    assert flags.ai_worker_paused is False
    assert flags.ai_worker_pause_reason is None
    assert flags.ai_worker_paused_at is None
    session.close()
