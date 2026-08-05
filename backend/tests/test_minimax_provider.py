import asyncio
import json

import httpx
import pytest

from app.services.ai.base import (
    ConfigurationError,
    ContentRejectedError,
    ProviderConfig,
    ProviderError,
    QuotaExhaustedError,
    RateLimitError,
)
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
        text_model="MiniMax-M3",
        image_model="image-01",
        speech_model="speech-2.8-turbo",
    ))

    result = asyncio.run(provider.text_to_speech("名词，港口"))

    assert result == audio
    assert captured["url"].endswith("/v1/t2a_v2")
    request_body = json.loads(captured["body"])
    assert request_body["output_format"] == "hex"
    assert request_body["language_boost"] == "Chinese"


def test_minimax_chat_defaults_to_m3(monkeypatch):
    from app.services.ai import minimax as minimax_module

    captured = {}

    def handler(request: httpx.Request):
        captured["body"] = json.loads(request.read().decode())
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "{}"}}],
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
        text_model="",
    ))

    assert asyncio.run(provider.chat([{"role": "user", "content": "test"}])) == "{}"
    assert captured["body"]["model"] == "MiniMax-M3"
    assert captured["body"]["max_completion_tokens"] == 1200
    assert captured["body"]["thinking"] == {"type": "disabled"}
    assert "max_tokens" not in captured["body"]


def test_minimax_image_downloads_temporary_url_without_leaking_api_key(monkeypatch):
    from app.services.ai import minimax as minimax_module

    image = b"\x89PNG\r\n\x1a\n" + (b"image" * 40)
    cdn_authorization = None

    def handler(request: httpx.Request):
        nonlocal cdn_authorization
        if str(request.url).endswith("/v1/image_generation"):
            return httpx.Response(200, json={
                "data": {"image_urls": ["https://cdn.hailuoai.com/generated/test.png"]},
                "metadata": {"failed_count": "0", "success_count": "1"},
                "base_resp": {"status_code": 0},
            })
        cdn_authorization = request.headers.get("authorization")
        return httpx.Response(
            200,
            content=image,
            headers={"content-type": "image/png"},
        )

    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        minimax_module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: real_client(transport=transport),
    )
    provider = MiniMaxProvider(ProviderConfig(
        api_key="secret-test-key",
        api_base="https://api.minimaxi.com",
        image_model="image-01",
    ))

    result = asyncio.run(provider.generate_image("one red boat, no text"))

    assert result == image
    assert cdn_authorization is None


def test_minimax_image_reports_content_review_without_key_error(monkeypatch):
    from app.services.ai import minimax as minimax_module

    def handler(_request: httpx.Request):
        return httpx.Response(200, json={
            "data": {},
            "metadata": {"failed_count": "1", "success_count": "0"},
            "base_resp": {"status_code": 0, "status_msg": "success"},
        })

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
        image_model="image-01",
    ))

    with pytest.raises(ContentRejectedError) as exc_info:
        asyncio.run(provider.generate_image("rejected prompt"))

    assert exc_info.value.code == "image_content_rejected"


def test_minimax_image_reports_unknown_success_shape_as_provider_error(monkeypatch):
    from app.services.ai import minimax as minimax_module

    def handler(_request: httpx.Request):
        return httpx.Response(200, json={
            "data": {"unexpected": []},
            "metadata": {"failed_count": "0", "success_count": "1"},
            "base_resp": {"status_code": 0},
        })

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
        image_model="image-01",
    ))

    with pytest.raises(ProviderError) as exc_info:
        asyncio.run(provider.generate_image("one red boat"))

    assert exc_info.value.code == "invalid_image_response"
    assert "unexpected" in str(exc_info.value)


def test_minimax_error_codes_have_distinct_retry_policy():
    with pytest.raises(RateLimitError):
        _raise_for_body_error(
            {"base_resp": {"status_code": 2045, "status_msg": "busy"}},
            "image",
        )
    with pytest.raises(RateLimitError):
        _raise_for_body_error(
            {"base_resp": {"status_code": 1013, "status_msg": "internal"}},
            "chat",
        )
    with pytest.raises(QuotaExhaustedError):
        _raise_for_body_error(
            {"base_resp": {"status_code": 2056, "status_msg": "plan exhausted"}},
            "image",
        )
    with pytest.raises(ConfigurationError):
        _raise_for_body_error(
            {"base_resp": {"status_code": 1004, "status_msg": "invalid key"}},
            "image",
        )
    with pytest.raises(ContentRejectedError):
        _raise_for_body_error(
            {"base_resp": {"status_code": 1027, "status_msg": "sensitive"}},
            "image",
        )


def test_chat_json_strips_reasoning_but_rejects_truncated_payload(monkeypatch):
    from app.services.ai import minimax as minimax_module

    responses = iter([
        '<think>{"draft": true}</think>{"ok": true}',
        '{"ok":',
    ])

    def handler(_request: httpx.Request):
        return httpx.Response(200, json={
            "choices": [{"message": {"content": next(responses)}}],
            "base_resp": {"status_code": 0, "status_msg": "success"},
        })

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
        text_model="MiniMax-M3",
    ))

    assert asyncio.run(provider.chat_json([{"role": "user", "content": "test"}])) == {"ok": True}
    with pytest.raises(RuntimeError, match="incomplete AI output was rejected"):
        asyncio.run(provider.chat_json([{"role": "user", "content": "test"}]))


def test_minimax_requests_are_single_flight_across_capabilities(monkeypatch):
    from app.services.ai import minimax as minimax_module

    active = 0
    maximum_active = 0
    image = b"\x89PNG\r\n\x1a\n" + (b"image" * 40)

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def request(self, method, url, **kwargs):
            nonlocal active, maximum_active
            active += 1
            maximum_active = max(maximum_active, active)
            await asyncio.sleep(0.02)
            active -= 1
            if url.endswith("/v1/image_generation"):
                import base64
                return httpx.Response(200, json={
                    "data": {"image_base64": [base64.b64encode(image).decode()]},
                    "base_resp": {"status_code": 0},
                })
            return httpx.Response(200, json={
                "choices": [{"message": {"content": "story"}}],
                "base_resp": {"status_code": 0},
            })

    monkeypatch.setattr(minimax_module.httpx, "AsyncClient", FakeClient)
    provider = MiniMaxProvider(ProviderConfig(
        api_key="test",
        api_base="https://api.minimaxi.com",
        text_model="MiniMax-M3",
        image_model="image-01",
    ))

    async def run_requests():
        return await asyncio.gather(
            provider.chat([{"role": "user", "content": "test"}]),
            provider.generate_image("one red boat, no text"),
        )

    result = asyncio.run(run_requests())

    assert result == ["story", image]
    assert maximum_active == 1


def test_interactive_text_does_not_wait_indefinitely_behind_media(monkeypatch):
    from app.services.ai import minimax as minimax_module

    image_started = None
    release_image = None
    image = b"\x89PNG\r\n\x1a\n" + (b"image" * 40)

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def request(self, method, url, **kwargs):
            if url.endswith("/v1/image_generation"):
                import base64
                image_started.set()
                await release_image.wait()
                return httpx.Response(200, json={
                    "data": {"image_base64": [base64.b64encode(image).decode()]},
                    "base_resp": {"status_code": 0},
                })
            return httpx.Response(200, json={
                "choices": [{"message": {"content": "story"}}],
                "base_resp": {"status_code": 0},
            })

    monkeypatch.setattr(minimax_module.httpx, "AsyncClient", FakeClient)
    provider = MiniMaxProvider(ProviderConfig(
        api_key="test",
        api_base="https://api.minimaxi.com",
        text_model="MiniMax-M3",
        image_model="image-01",
    ))

    async def run_requests():
        nonlocal image_started, release_image
        image_started = asyncio.Event()
        release_image = asyncio.Event()
        image_task = asyncio.create_task(provider.generate_image("one red boat, no text"))
        await image_started.wait()
        try:
            with pytest.raises(RateLimitError, match="request queue is busy"):
                await provider.chat(
                    [{"role": "user", "content": "test"}],
                    queue_timeout=0.01,
                )
        finally:
            release_image.set()
            await image_task

    asyncio.run(run_requests())
