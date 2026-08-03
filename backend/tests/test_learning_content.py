import time

from sqlalchemy import event

from app import models
from app.services.learning_content import (
    LearningContentResolver,
    MeaningNormalizer,
    backfill_legacy_memory,
    build_lexeme_key,
    coverage_for_bank,
    seed_word_evolution,
)


def test_meaning_normalizer_removes_raw_pos_examples_and_noise():
    result = MeaningNormalizer.normalize(
        "vt. 打开；开启（机器等）；He opened the heavy door.；打开"
    )

    assert result.normalized_pos == "及物动词"
    assert result.primary_meaning == "打开；开启"
    assert result.narration_text == "及物动词，打开；开启"
    assert "vt." not in result.narration_text
    assert "He" not in result.narration_text


def test_resolver_prefers_active_bundle_without_changing_word_facts(api):
    session = api["session"]()
    bank = models.WordBank(name="facts", user_id=api["user_id"], word_count=1)
    session.add(bank)
    session.flush()
    word = models.Word(
        bank_id=bank.id,
        seq_num=1,
        word="open",
        phonetic="/open/",
        meaning="vt. 打开；开启",
    )
    session.add(word)
    session.flush()
    key = build_lexeme_key("open", "及物动词", "打开；开启")
    bundle = models.MemoryBundle(
        lexeme_key=key,
        word_text="open",
        normalized_pos="及物动词",
        primary_meaning="打开；开启",
        strategy="direct",
        memory_anchor="一只手推开紧闭的门，直接对应“打开”",
        scene_summary="手推开门",
        image_prompt="One hand opens a red door, a bright brass key catches the light, no text.",
        narration_text="及物动词，打开；开启",
        prompt_version="memory-v1",
        content_version=1,
        status="active",
    )
    session.add(bundle)
    session.flush()
    session.add(models.WordMemoryLink(
        word_id=word.id,
        active_bundle_id=bundle.id,
        status="ready",
    ))
    session.add_all([
        models.MemoryAsset(
            bundle_id=bundle.id,
            asset_type="image",
            file_path="images/open.png",
            sha256="a" * 64,
            mime_type="image/png",
            version=1,
            status="ready",
        ),
        models.MemoryAsset(
            bundle_id=bundle.id,
            asset_type="audio",
            file_path="audio/open.mp3",
            sha256="b" * 64,
            mime_type="audio/mpeg",
            version=1,
            status="ready",
        ),
    ])
    session.commit()

    content = LearningContentResolver(session).resolve(word)
    session.refresh(word)

    assert content["source"] == "ai"
    assert content["image_url"] == "/ai-media/images/open.png"
    assert content["narration_audio_url"] == "/ai-media/audio/open.mp3"
    assert content["memory_anchor"].startswith("一只手")
    assert word.word == "open"
    assert word.phonetic == "/open/"
    assert word.meaning == "vt. 打开；开启"
    coverage = coverage_for_bank(session, bank.id)
    assert coverage["text_ready_percent"] == 100
    assert coverage["complete_ready_percent"] == 100
    session.close()


def test_legacy_resources_become_v1_without_reusing_raw_context_audio(
    api,
    monkeypatch,
    tmp_path,
):
    media_root = tmp_path / "ai-media"
    legacy_image = tmp_path / "legacy.png"
    legacy_image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"legacy-image")
    monkeypatch.setenv("AI_MEDIA_DIR", str(media_root))
    session = api["session"]()
    bank = models.WordBank(name="legacy", user_id=api["user_id"], word_count=1)
    session.add(bank)
    session.flush()
    word = models.Word(
        bank_id=bank.id,
        seq_num=1,
        word="calm",
        phonetic="/kɑːm/",
        meaning="adj. 平静的",
        mnemonic="平静的湖面没有波纹",
        image_prompt="legacy prompt",
        image_url=str(legacy_image),
        context_audio="/audio_context/calm.mp3",
        enriched=True,
    )
    session.add(word)
    session.commit()

    result = backfill_legacy_memory(session)
    content = LearningContentResolver(session).resolve(word)
    session.refresh(word)

    assert result["created"] == 1
    assert content["prompt_version"] == "legacy-v1"
    assert content["image_url"].startswith("/ai-media/images/legacy-bundle-")
    assert content["narration_audio_url"] is None
    assert word.context_audio == "/audio_context/calm.mp3"
    assert session.query(models.AiJob).filter_by(kind="audio").count() == 1
    session.close()


def test_same_lexeme_reuses_active_bundle(api):
    session = api["session"]()
    bank = models.WordBank(name="reuse", user_id=api["user_id"], word_count=2)
    session.add(bank)
    session.flush()
    words = [
        models.Word(bank_id=bank.id, seq_num=index, word="open", phonetic="", meaning="vt. 打开")
        for index in (1, 2)
    ]
    session.add_all(words)
    session.flush()
    normalized = MeaningNormalizer.normalize(words[0].meaning)
    bundle = models.MemoryBundle(
        lexeme_key=build_lexeme_key("open", normalized.normalized_pos, normalized.primary_meaning),
        word_text="open",
        normalized_pos=normalized.normalized_pos,
        primary_meaning=normalized.primary_meaning,
        strategy="direct",
        memory_anchor="推开门，表示打开",
        scene_summary="推门",
        image_prompt="A hand pushes open one red door, a brass hinge shines, no text.",
        narration_text=normalized.narration_text,
        prompt_version="memory-v1",
        content_version=1,
        status="active",
    )
    session.add(bundle)
    session.flush()

    assert seed_word_evolution(session, words[0]) == "reused"
    assert seed_word_evolution(session, words[1]) == "reused"
    session.commit()
    links = session.query(models.WordMemoryLink).order_by(models.WordMemoryLink.word_id).all()

    assert [link.active_bundle_id for link in links] == [bundle.id, bundle.id]
    assert session.query(models.AiJob).filter(models.AiJob.kind == "bundle_text").count() == 0
    session.close()


def test_large_bank_coverage_uses_one_fast_aggregate_query(api):
    session = api["session"]()
    bank = models.WordBank(
        name="large",
        user_id=api["user_id"],
        word_count=10_000,
    )
    session.add(bank)
    session.flush()
    bank_id = bank.id
    session.bulk_insert_mappings(
        models.Word,
        [
            {
                "bank_id": bank_id,
                "seq_num": index,
                "word": f"word-{index}",
                "phonetic": "",
                "meaning": "n. 测试",
            }
            for index in range(1, 10_001)
        ],
    )
    session.commit()

    statements = []

    def count_statement(*_args):
        statements.append(1)

    event.listen(session.bind, "before_cursor_execute", count_statement)
    started = time.perf_counter()
    try:
        coverage = coverage_for_bank(session, bank_id)
    finally:
        elapsed = time.perf_counter() - started
        event.remove(session.bind, "before_cursor_execute", count_statement)

    assert coverage["total"] == 10_000
    assert coverage["text_ready"] == 0
    assert coverage["visual_ready"] == 0
    assert coverage["complete_ready"] == 0
    assert len(statements) == 1
    assert elapsed < 0.5
    session.close()


def test_admin_can_edit_preview_and_activate_a_complete_version(api):
    session = api["session"]()
    bank = models.WordBank(name="admin", user_id=api["user_id"], word_count=1)
    session.add(bank)
    session.flush()
    word = models.Word(bank_id=bank.id, seq_num=1, word="clear", phonetic="", meaning="adj. 清晰的")
    session.add(word)
    session.flush()
    bundle = models.MemoryBundle(
        lexeme_key=build_lexeme_key("clear", "形容词", "清晰的"),
        word_text="clear",
        normalized_pos="形容词",
        primary_meaning="清晰的",
        strategy="direct",
        memory_anchor="擦净玻璃后景物变清晰",
        scene_summary="擦净玻璃",
        image_prompt="One hand wipes one glass pane, revealing a sharp red tower, no text.",
        narration_text="形容词，清晰的",
        prompt_version="memory-v1",
        content_version=1,
        status="active",
    )
    session.add(bundle)
    session.flush()
    session.add(models.WordMemoryLink(word_id=word.id, active_bundle_id=bundle.id, status="ready"))
    session.add_all([
        models.MemoryAsset(
            bundle_id=bundle.id,
            asset_type="image",
            file_path="images/clear.png",
            sha256="c" * 64,
            mime_type="image/png",
            version=1,
            status="ready",
        ),
        models.MemoryAsset(
            bundle_id=bundle.id,
            asset_type="audio",
            file_path="audio/clear.mp3",
            sha256="d" * 64,
            mime_type="audio/mpeg",
            version=1,
            status="ready",
        ),
    ])
    feedback = models.MemoryFeedback(
        user_id=api["user_id"],
        word_id=word.id,
        bundle_id=bundle.id,
        component="memory_anchor",
        reason="记忆点牵强",
        status="manual_review",
    )
    session.add(feedback)
    session.commit()
    source_id, word_id = bundle.id, word.id
    session.close()

    edited = api["client"].put(
        f"/api/ai/evolution/bundles/{source_id}",
        headers=api["headers"],
        json={"memory_anchor": "擦净雾气，远处红塔立刻变得清晰"},
    )
    assert edited.status_code == 200
    draft_id = edited.json()["bundle_id"]
    versions = api["client"].get(
        f"/api/ai/evolution/words/{word_id}/versions",
        headers=api["headers"],
    ).json()
    draft = next(item for item in versions["items"] if item["id"] == draft_id)
    assert {asset["type"] for asset in draft["assets"]} == {"image", "audio"}

    activated = api["client"].post(
        f"/api/ai/evolution/words/{word_id}/activate/{draft_id}",
        headers=api["headers"],
        json={"expected_active_bundle_id": versions["active_bundle_id"]},
    )
    assert activated.status_code == 200
    stale_rollback = api["client"].post(
        f"/api/ai/evolution/words/{word_id}/rollback/{source_id}",
        headers=api["headers"],
        json={"expected_active_bundle_id": source_id},
    )
    assert stale_rollback.status_code == 409
    assert stale_rollback.json()["code"] == "stale_revision"
    assert stale_rollback.json()["current"]["active_bundle_id"] == draft_id
    session = api["session"]()
    assert session.query(models.WordMemoryLink).filter_by(word_id=word_id).one().active_bundle_id == draft_id
    assert session.get(models.MemoryBundle, source_id).status == "archived"
    assert session.query(models.MemoryFeedback).filter_by(word_id=word_id).one().status == "resolved"
    session.close()


def test_admin_cannot_activate_same_spelling_for_a_different_meaning(api):
    session = api["session"]()
    bank = models.WordBank(name="homograph", user_id=api["user_id"], word_count=1)
    session.add(bank)
    session.flush()
    word = models.Word(
        bank_id=bank.id,
        seq_num=1,
        word="bank",
        phonetic="",
        meaning="n. 银行",
    )
    session.add(word)
    session.flush()
    river_bundle = models.MemoryBundle(
        lexeme_key=build_lexeme_key("bank", "名词", "河岸"),
        word_text="bank",
        normalized_pos="名词",
        primary_meaning="河岸",
        strategy="direct",
        memory_anchor="河水拍打河岸",
        scene_summary="河岸",
        image_prompt="A river touches one grassy bank beside one red stone, no text.",
        narration_text="名词，河岸",
        prompt_version="memory-v1",
        content_version=1,
        status="active",
    )
    session.add(river_bundle)
    session.flush()
    session.add_all([
        models.MemoryAsset(
            bundle_id=river_bundle.id,
            asset_type="image",
            file_path="images/river-bank.png",
            sha256="e" * 64,
            mime_type="image/png",
            version=1,
            status="ready",
        ),
        models.MemoryAsset(
            bundle_id=river_bundle.id,
            asset_type="audio",
            file_path="audio/river-bank.mp3",
            sha256="f" * 64,
            mime_type="audio/mpeg",
            version=1,
            status="ready",
        ),
    ])
    session.commit()
    word_id, bundle_id = word.id, river_bundle.id
    session.close()

    response = api["client"].post(
        f"/api/ai/evolution/words/{word_id}/activate/{bundle_id}",
        headers=api["headers"],
        json={"expected_active_bundle_id": None},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "记忆包词义与当前单词不一致"
