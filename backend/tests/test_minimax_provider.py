import asyncio
import json

import httpx
import pytest

from app.services.ai.base import ProviderConfig, ProviderError, QuotaExhaustedError, RateLimitError
from app.services.ai.minimax import MiniMaxProvider, _raise_for_body_error


def test_minimax_tts_uses_t2a_v2_and_decodes_hex(monkeypatch):
    from app.services.ai import minimax as minimax_module

    captured = {}
    audio = b"ID3" + (b"voice" * 30)

    def handler(request: httpx.Request):
        captured["url"] = str(request.url)
        captured["body"] = request.read().decode()
        return httpx.Response(
            200,
            json={
                "data": {"audio": audio.hex()},
                "base_resp": {"status_code": 0, "status_msg": "success"},
            },
        )

    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        minimax_module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: real_client(transport=transport),
    )
    provider = MiniMaxProvider(ProviderConfig(
        api_key="test",
        api_base="https://api.minimaxi.com",
        text_model="MiniMax-M2.7",
        image_model="image-01",
        speech_model="speech-2.8-turbo",
    ))

    result = asyncio.run(provider.text_to_speech("名词，港口"))

    assert result == audio
    assert captured["url"].endswith("/v1/t2a_v2")
    request_body = json.loads(captured["body"])
    assert request_body["output_format"] == "hex"
    assert request_body["language_boost"] == "Chinese"


def test_minimax_error_codes_have_distinct_retry_policy():
    with pytest.raises(RateLimitError):
        _raise_for_body_error(
            {"base_resp": {"status_code": 2045, "status_msg": "busy"}},
            "image",
        )
    with pytest.raises(QuotaExhaustedError):
        _raise_for_body_error(
            {"base_resp": {"status_code": 2056, "status_msg": "plan exhausted"}},
            "image",
        )
    with pytest.raises(ProviderError):
        _raise_for_body_error(
            {"base_resp": {"status_code": 1004, "status_msg": "invalid key"}},
            "image",
        )
