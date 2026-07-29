"""MiniMax China provider: text, Image-01, Speech 2.8 and plan quota."""
import base64
from typing import Any

import httpx

from .base import (
    BaseProvider,
    ProviderError,
    QuotaExhaustedError,
    RateLimitError,
)


def _parse_rate_limit_headers(headers) -> tuple[bool, float]:
    """从响应头解析速率限制信息. 返回 (is_rate_limited, retry_after_seconds)"""
    h = {k.lower(): v for k, v in (headers.items() if headers else [])}
    # 标准 Retry-After
    retry_after = h.get("retry-after")
    if retry_after:
        try:
            return True, float(retry_after)
        except (ValueError, TypeError):
            return True, 60.0
    # MiniMax 风格的限流标记
    for k in ("x-ratelimit-remaining", "x-request-cost", "x-quota-remaining"):
        v = h.get(k)
        if v is not None and v != "":
            try:
                if float(v) <= 0:
                    return True, 60.0
            except (ValueError, TypeError):
                pass
    return False, 0.0


def _raise_for_http_error(resp: httpx.Response, operation: str) -> None:
    if resp.status_code == 429:
        _, retry = _parse_rate_limit_headers(resp.headers)
        raise RateLimitError(
            f"MiniMax {operation} 429 Too Many Requests",
            retry_after=retry or 60.0,
        )
    if resp.status_code >= 500:
        raise RateLimitError(
            f"MiniMax {operation} service unavailable ({resp.status_code})",
            retry_after=60.0,
        )
    if resp.status_code >= 400:
        raise ProviderError(
            f"MiniMax {operation} HTTP {resp.status_code}",
            code=f"http_{resp.status_code}",
        )


TRANSIENT_CODES = {1000, 1001, 1002, 1024, 1033, 2045}
QUOTA_CODES = {2056}


def _base_response(data: Any) -> dict:
    if not isinstance(data, dict):
        return {}
    base = data.get("base_resp") or data
    return base if isinstance(base, dict) else {}


def _raise_for_body_error(data: Any, operation: str) -> None:
    base = _base_response(data)
    status_code = base.get("status_code")
    if status_code in (None, 0, "0"):
        return
    try:
        code = int(status_code)
    except (ValueError, TypeError):
        raise ProviderError(f"MiniMax {operation} 返回未知错误码: {status_code}")
    message = (
        base.get("status_msg")
        or base.get("message")
        or f"MiniMax {operation} failed"
    )
    if code in QUOTA_CODES:
        raise QuotaExhaustedError(message, code=str(code))
    if code in TRANSIENT_CODES:
        raise RateLimitError(
            f"MiniMax {operation} 暂时不可用 ({code}): {message}",
            retry_after=60.0,
        )
    raise ProviderError(
        f"MiniMax {operation} 配置或请求错误 ({code}): {message}",
        code=str(code),
    )


class MiniMaxProvider(BaseProvider):
    """MiniMax API

    文本模型: MiniMax-M3
    图像生成: image-01
    语音合成: speech-2.8-turbo
    """

    def _endpoint(self, path: str) -> str:
        base = self.config.api_base.rstrip("/")
        return f"{base}{path}"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

    async def chat(self, messages: list[dict], **kwargs) -> str:
        model = kwargs.pop("model", self.config.text_model or "MiniMax-M3")
        async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
            resp = await client.post(
                self._endpoint("/v1/text/chatcompletion_v2"),
                headers=self._headers(),
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": kwargs.get("max_tokens", 2048),
                    "temperature": kwargs.get("temperature", 0.7),
                },
            )
            # 速率限制检测
            limited, retry = _parse_rate_limit_headers(resp.headers)
            if limited:
                raise RateLimitError(f"MiniMax chat rate limited (retry after {retry}s)", retry_after=retry)
            _raise_for_http_error(resp, "chat")
            data = resp.json()
            _raise_for_body_error(data, "chat")
            return data["choices"][0]["message"]["content"]

    async def generate_image(self, prompt: str, **kwargs) -> bytes:
        """MiniMax Image-01 图像生成, 返回 PNG 二进制"""
        model = kwargs.pop("model", self.config.image_model or "image-01")
        async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
            resp = await client.post(
                self._endpoint("/v1/image_generation"),
                headers=self._headers(),
                json={
                    "model": model,
                    "prompt": prompt,
                    "n": kwargs.get("n", 1),
                    "aspect_ratio": kwargs.get("aspect_ratio", "1:1"),
                    "response_format": "base64",
                },
            )
            limited, retry = _parse_rate_limit_headers(resp.headers)
            if limited:
                raise RateLimitError(f"MiniMax image rate limited (retry after {retry}s)", retry_after=retry)
            _raise_for_http_error(resp, "image")
            data = resp.json()
            _raise_for_body_error(data, "image")
            b64 = data["data"]["image_base64"][0]
            content = base64.b64decode(b64)
            if len(content) < 100 or content[:1] not in (b"\x89", b"\xff", b"R"):
                raise ProviderError("MiniMax image returned invalid image bytes")
            return content

    async def text_to_speech(self, text: str, **kwargs) -> bytes:
        """MiniMax Speech 2.8 T2A v2, whose audio field defaults to hex."""
        model = kwargs.pop("model", self.config.speech_model or "speech-2.8-turbo")
        voice = kwargs.pop("voice", "Chinese (Mandarin)_Warm_Girl")
        async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
            resp = await client.post(
                self._endpoint("/v1/t2a_v2"),
                headers=self._headers(),
                json={
                    "model": model,
                    "text": text,
                    "voice_setting": {
                        "voice_id": voice,
                        "speed": kwargs.get("speed", 1.0),
                        "vol": kwargs.get("volume", 1.0),
                        "pitch": kwargs.get("pitch", 0),
                    },
                    "audio_setting": {
                        "audio_sample_rate": 32000,
                        "bitrate": 128000,
                        "format": "mp3",
                        "channel": 1,
                    },
                    "language_boost": "Chinese",
                    "output_format": "hex",
                },
            )
            limited, retry = _parse_rate_limit_headers(resp.headers)
            if limited:
                raise RateLimitError(f"MiniMax TTS rate limited (retry after {retry}s)", retry_after=retry)
            _raise_for_http_error(resp, "speech")
            data = resp.json()

            _raise_for_body_error(data, "speech")
            audio_hex = (data.get("data") or {}).get("audio")
            if not audio_hex:
                raise ProviderError("MiniMax speech response has no audio")
            try:
                content = bytes.fromhex(audio_hex)
            except ValueError as exc:
                raise ProviderError("MiniMax speech returned invalid hex audio") from exc
            if len(content) < 100:
                raise ProviderError("MiniMax speech returned empty audio")
            return content

    async def get_quota(self) -> dict:
        """Return the raw Token Plan remaining payload from the China account site."""

        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            resp = await client.get(
                "https://www.minimaxi.com/v1/token_plan/remains",
                headers=self._headers(),
            )
            _raise_for_http_error(resp, "quota")
            data = resp.json()
            _raise_for_body_error(data, "quota")
            return data
