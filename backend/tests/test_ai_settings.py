from app import models
from app.services.ai.secrets import decrypt_secret


def test_api_key_is_encrypted_and_blank_update_preserves_it(api):
    payload = {
        "provider": "minimax",
        "api_key": "secret-minimax-key",
        "api_base": "https://api.minimax.chat",
        "text_model": "minimax-m2.7",
        "image_model": "",
        "speech_model": "speech-02",
        "is_enabled": True,
    }
    created = api["client"].post(
        "/api/settings/ai-configs",
        headers=api["headers"],
        json=payload,
    )
    assert created.status_code == 200

    session = api["session"]()
    config = session.query(models.ApiConfig).filter_by(provider="minimax").one()
    encrypted = config.api_key_encrypted
    assert encrypted.startswith("enc:v1:")
    assert "secret-minimax-key" not in encrypted
    assert decrypt_secret(encrypted) == "secret-minimax-key"
    assert config.api_base == "https://api.minimaxi.com"
    assert config.text_model == "MiniMax-M3"
    assert config.image_model == "image-01"
    assert config.speech_model == "speech-2.8-turbo"
    session.close()

    listed = api["client"].get(
        "/api/settings/ai-configs",
        headers=api["headers"],
    )
    assert listed.status_code == 200
    assert listed.json()[0]["has_api_key"] is True
    assert "api_key_masked" not in listed.json()[0]

    payload["api_key"] = None
    payload["speech_model"] = "speech-2.8-hd"
    updated = api["client"].post(
        "/api/settings/ai-configs",
        headers=api["headers"],
        json=payload,
    )
    assert updated.status_code == 200

    session = api["session"]()
    config = session.query(models.ApiConfig).filter_by(provider="minimax").one()
    assert config.api_key_encrypted == encrypted
    assert config.speech_model == "speech-2.8-hd"
    session.close()
