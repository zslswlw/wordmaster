import asyncio
from types import SimpleNamespace

from app import models
from app.clock import utc_now
from app.services.ai import MemoryBundleCandidate, MemoryQualityScores
from app.services.ai.worker import AiJobProcessor
from app.services.learning_content import (
    LearningContentResolver,
    queue_ai_job,
    seed_word_evolution,
)


class FakeMiniMax:
    config = SimpleNamespace(
        text_model="MiniMax-M2.7",
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

    async def generate_memory_candidate(self, word, feedback_context=""):
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


def _run(coro):
    return asyncio.run(coro)


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
    assert worker.json()["state"] == "queued"
    assert worker.json()["queue"]["next_job"]["id"] == job_id
