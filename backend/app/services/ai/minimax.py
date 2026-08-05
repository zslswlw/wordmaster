"""MiniMax China provider: text, Image-01, Speech 2.8 and plan quota."""
import asyncio
import base64
import binascii
import threading
import weakref
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from .base import (
    BaseProvider,
    ConfigurationError,
    ContentRejectedError,
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
    if resp.status_code in {401, 403, 404}:
        raise ConfigurationError(
            f"MiniMax {operation} HTTP {resp.status_code}",
            code=f"http_{resp.status_code}",
        )
    if resp.status_code >= 400:
        raise ProviderError(
            f"MiniMax {operation} HTTP {resp.status_code}",
            code=f"http_{resp.status_code}",
        )


TRANSIENT_CODES = {1000, 1001, 1002, 1013, 1024, 1033, 2045}
QUOTA_CODES = {2056}
CONFIGURATION_CODES = {1004, 1039, 2013}
CONTENT_REJECTED_CODES = {1026, 1027}


_REQUEST_LOCKS: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
_REQUEST_LOCKS_GUARD = threading.Lock()


def _request_lock() -> asyncio.Lock:
    """Keep all MiniMax capabilities single-flight inside one app process."""

    loop = asyncio.get_running_loop()
    with _REQUEST_LOCKS_GUARD:
        lock = _REQUEST_LOCKS.get(loop)
        if lock is None:
            lock = asyncio.Lock()
            _REQUEST_LOCKS[loop] = lock
        return lock


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
    if code in CONTENT_REJECTED_CODES:
        raise ContentRejectedError(
            f"MiniMax {operation} 内容未通过审核 ({code}): {message}",
            code=str(code),
        )
    if code in CONFIGURATION_CODES:
        raise ConfigurationError(
            f"MiniMax {operation} 配置或请求参数错误 ({code}): {message}",
            code=str(code),
        )
    raise ProviderError(
        f"MiniMax {operation} 配置或请求错误 ({code}): {message}",
        code=str(code),
    )


def _first_string(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, list):
        return next(
            (item.strip() for item in value if isinstance(item, str) and item.strip()),
            None,
        )
    return None


def _metadata_count(metadata: dict, name: str) -> int:
    try:
        return int(metadata.get(name) or 0)
    except (TypeError, ValueError):
        return 0


def _validated_image_bytes(content: bytes) -> bytes:
    signatures = (b"\x89PNG", b"\xff\xd8\xff", b"RIFF", b"GIF8")
    if len(content) < 100 or not content.startswith(signatures):
        raise ProviderError(
            "MiniMax image returned invalid image bytes",
            code="invalid_image_bytes",
        )
    if len(content) > 25 * 1024 * 1024:
        raise ProviderError(
            "MiniMax image exceeded the 25 MB safety limit",
            code="image_too_large",
        )
    return content


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

    async def _request(
        self,
        method: str,
        url: str,
        *,
        timeout: float,
        json_payload: Optional[dict] = None,
        queue_timeout: Optional[float] = None,
    ) -> httpx.Response:
        async def send() -> httpx.Response:
            async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                return await client.request(
                    method,
                    url,
                    headers=self._headers(),
                    json=json_payload,
                )

        lock = _request_lock()
        if queue_timeout is None:
            async with lock:
                return await send()
        try:
            await asyncio.wait_for(lock.acquire(), timeout=queue_timeout)
        except asyncio.TimeoutError as exc:
            raise RateLimitError(
                "MiniMax request queue is busy",
                retry_after=queue_timeout,
            ) from exc
        try:
            return await send()
        finally:
            lock.release()

    async def chat(self, messages: list[dict], **kwargs) -> str:
        model = kwargs.pop("model", self.config.text_model or "MiniMax-M3")
        max_completion_tokens = kwargs.get(
            "max_completion_tokens",
            kwargs.get("max_tokens", 1200),
        )
        payload = {
            "model": model,
            "messages": messages,
            "max_completion_tokens": max_completion_tokens,
            "temperature": kwargs.get("temperature", 0.7),
        }
        if model.lower() == "minimax-m3":
            payload["thinking"] = kwargs.get("thinking", {"type": "disabled"})
        resp = await self._request(
            "POST",
            self._endpoint("/v1/text/chatcompletion_v2"),
            timeout=90,
            json_payload=payload,
            queue_timeout=kwargs.get("queue_timeout"),
        )
        limited, retry = _parse_rate_limit_headers(resp.headers)
        if limited:
            raise RateLimitError(f"MiniMax chat rate limited (retry after {retry}s)", retry_after=retry)
        _raise_for_http_error(resp, "chat")
        data = resp.json()
        _raise_for_body_error(data, "chat")
        return data["choices"][0]["message"]["content"]

    async def generate_image(self, prompt: str, **kwargs) -> bytes:
        """Generate one image and normalize base64 or temporary-URL responses."""
        model = kwargs.pop("model", self.config.image_model or "image-01")
        resp = await self._request(
            "POST",
            self._endpoint("/v1/image_generation"),
            timeout=120,
            json_payload={
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
        image_data = data.get("data") if isinstance(data, dict) else None
        image_data = image_data if isinstance(image_data, dict) else {}

        encoded = _first_string(image_data.get("image_base64"))
        if encoded:
            if encoded.startswith("data:") and "," in encoded:
                encoded = encoded.split(",", 1)[1]
            try:
                content = base64.b64decode("".join(encoded.split()), validate=True)
            except (binascii.Error, ValueError) as exc:
                raise ProviderError(
                    "MiniMax image returned invalid base64",
                    code="invalid_image_base64",
                ) from exc
            return _validated_image_bytes(content)

        image_url = (
            _first_string(image_data.get("image_urls"))
            or _first_string(image_data.get("image_url"))
        )
        if image_url:
            return await self._download_image(image_url)

        metadata = data.get("metadata") if isinstance(data, dict) else None
        metadata = metadata if isinstance(metadata, dict) else {}
        failed_count = _metadata_count(metadata, "failed_count")
        success_count = _metadata_count(metadata, "success_count")
        if failed_count > 0 and success_count == 0:
            raise ContentRejectedError(
                "MiniMax image content safety review returned no image",
                code="image_content_rejected",
            )

        fields = sorted(str(key) for key in image_data)
        raise ProviderError(
            "MiniMax image response contained no image asset "
            f"(data fields: {fields or ['none']}, success_count: {success_count}, "
            f"failed_count: {failed_count})",
            code="invalid_image_response",
        )

    async def _download_image(self, image_url: str) -> bytes:
        parsed = urlparse(image_url)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ProviderError(
                "MiniMax returned an invalid image URL",
                code="invalid_image_url",
            )

        async with _request_lock():
            async with httpx.AsyncClient(
                timeout=60,
                trust_env=False,
                follow_redirects=True,
            ) as client:
                resp = await client.get(image_url, headers={"Accept": "image/*"})
        if resp.status_code == 429 or resp.status_code >= 500:
            raise RateLimitError(
                f"MiniMax image download temporarily unavailable ({resp.status_code})",
                retry_after=60.0,
            )
        if resp.status_code >= 400:
            raise ProviderError(
                f"MiniMax image URL HTTP {resp.status_code}",
                code="image_url_unavailable",
            )
        content_type = resp.headers.get("content-type", "").lower()
        if content_type and not (
            content_type.startswith("image/")
            or content_type.startswith("application/octet-stream")
        ):
            raise ProviderError(
                f"MiniMax image URL returned {content_type}",
                code="invalid_image_content_type",
            )
        return _validated_image_bytes(resp.content)

    async def text_to_speech(self, text: str, **kwargs) -> bytes:
        """MiniMax Speech 2.8 T2A v2, whose audio field defaults to hex."""
        model = kwargs.pop("model", self.config.speech_model or "speech-2.8-turbo")
        voice = kwargs.pop("voice", "Chinese (Mandarin)_Warm_Girl")
        resp = await self._request(
            "POST",
            self._endpoint("/v1/t2a_v2"),
            timeout=60,
            json_payload={
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

        resp = await self._request(
            "GET",
            "https://www.minimaxi.com/v1/token_plan/remains",
            timeout=30,
        )
        _raise_for_http_error(resp, "quota")
        data = resp.json()
        _raise_for_body_error(data, "quota")
        return data
