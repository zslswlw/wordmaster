import hashlib
import io
import json
import zipfile

from app import models
from app.services.learning_content import LearningContentResolver, build_lexeme_key


def test_full_backup_contains_media_manifest_and_restores_links(api, monkeypatch, tmp_path):
    media_root = tmp_path / "ai-media"
    monkeypatch.setenv("AI_MEDIA_DIR", str(media_root))
    session = api["session"]()
    bank = models.WordBank(name="backup", user_id=api["user_id"], word_count=1)
    session.add(bank)
    session.flush()
    word = models.Word(
        bank_id=bank.id,
        seq_num=1,
        word="bright",
        phonetic="/braɪt/",
        meaning="adj. 明亮的",
    )
    session.add(word)
    session.flush()
    bundle = models.MemoryBundle(
        lexeme_key=build_lexeme_key("bright", "形容词", "明亮的"),
        word_text="bright",
        normalized_pos="形容词",
        primary_meaning="明亮的",
        strategy="direct",
        memory_anchor="一盏灯照亮房间，对应明亮",
        scene_summary="灯照亮房间",
        image_prompt="One lamp brightly illuminates one room with a red chair, no text.",
        narration_text="形容词，明亮的",
        prompt_version="memory-v1",
        content_version=1,
        status="active",
    )
    session.add(bundle)
    session.flush()
    content = b"\x89PNG\r\n\x1a\n" + b"backup-image"
    relative = "images/bright.png"
    path = media_root / relative
    path.parent.mkdir(parents=True)
    path.write_bytes(content)
    session.add(models.MemoryAsset(
        bundle_id=bundle.id,
        asset_type="image",
        file_path=relative,
        sha256=hashlib.sha256(content).hexdigest(),
        mime_type="image/png",
        version=1,
        status="ready",
    ))
    session.add(models.WordMemoryLink(
        word_id=word.id,
        active_bundle_id=bundle.id,
        status="generating_assets",
    ))
    session.commit()
    session.close()

    response = api["client"].post("/api/backup/export-full", headers=api["headers"])
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert {"backup.json", "manifest.json", f"media/{relative}"}.issubset(
            archive.namelist()
        )
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["files"][0]["sha256"] == hashlib.sha256(content).hexdigest()

    restored = api["client"].post(
        "/api/backup/import",
        headers=api["headers"],
        files={"file": ("wordmaster.zip", response.content, "application/zip")},
    )
    assert restored.status_code == 200

    session = api["session"]()
    restored_word = session.query(models.Word).filter_by(word="bright").one()
    learning_content = LearningContentResolver(session).resolve(restored_word)
    assert restored_word.phonetic == "/braɪt/"
    assert restored_word.meaning == "adj. 明亮的"
    assert learning_content["memory_anchor"] == "一盏灯照亮房间，对应明亮"
    assert learning_content["image_url"] == "/ai-media/images/bright.png"
    session.close()
