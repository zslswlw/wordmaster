import asyncio

import httpx
import pytest

from app.services.ai.base import ConfigurationError, ProviderConfig, RateLimitError
from app.services.ai.deepseek import DeepSeekProvider


@pytest.mark.parametrize(
    ("status_code", "error_type"),
    ((401, ConfigurationError), (503, RateLimitError)),
)
def test_deepseek_distinguishes_configuration_and_transient_errors(
    monkeypatch,
    status_code,
    error_type,
):
    from app.services.ai import deepseek as deepseek_module

    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(status_code, json={"message": "failed"})
    )
    monkeypatch.setattr(
        deepseek_module.httpx,
        "AsyncClient",
        lambda *args, **kwargs: real_client(transport=transport),
    )
    provider = DeepSeekProvider(ProviderConfig(
        api_key="test",
        api_base="https://api.deepseek.com",
        text_model="deepseek-chat",
    ))

    with pytest.raises(error_type):
        asyncio.run(provider.chat([{"role": "user", "content": "test"}]))
