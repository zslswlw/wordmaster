"""MiniMax Provider — 文本 + 图像生成 + TTS"""
import httpx
from .base import BaseProvider, ProviderConfig, RateLimitError, ProviderError


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
        if v is not None and v not in ("0", ""):
            try:
                if float(v) <= 0:
                    return True, 60.0
            except (ValueError, TypeError):
                pass
    return False, 0.0


def _check_rate_limit_in_body(data) -> tuple[bool, float]:
    """从响应体解析 MiniMax 的 base_resp 错误码识别限流.
    常见 status_code: 1004 (限流), 1008 (余额), 1039 (token rate) 等.
    任何 status_code > 0 (且不是 success 的 0) 都视为需要处理.
    """
    if not isinstance(data, dict):
        return False, 0.0
    base = data.get("base_resp") or data
    if not isinstance(base, dict):
        return False, 0.0
    status_code = base.get("status_code")
    if status_code is None:
        return False, 0.0
    try:
        code = int(status_code)
    except (ValueError, TypeError):
        return False, 0.0
    # 显式限流 / 配额类
    if code in (1002, 1003, 1004, 1008, 1013, 1024, 1025, 1039):
        return True, 60.0
    # 任何非 0 错误码都视作 API 错误 (含限流) — 让上层按 rate_limited 处理
    if code != 0:
        return True, 60.0
    return False, 0.0


class MiniMaxProvider(BaseProvider):
    """MiniMax API

    文本模型: minimax-m2, minimax-m2.7
    图像生成: image-01
    语音合成: speech-02
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
        model = kwargs.pop("model", self.config.text_model or "minimax-m2")
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
            if resp.status_code == 429:
                raise RateLimitError("MiniMax chat 429 Too Many Requests", retry_after=retry or 60.0)
            resp.raise_for_status()
            data = resp.json()
            # body-level 限流检测
            limited, retry = _check_rate_limit_in_body(data)
            if limited:
                raise RateLimitError(f"MiniMax chat base_resp rate limit (retry after {retry}s)", retry_after=retry)
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
            if resp.status_code == 429:
                raise RateLimitError("MiniMax image 429 Too Many Requests", retry_after=retry or 60.0)
            resp.raise_for_status()
            data = resp.json()
            limited, retry = _check_rate_limit_in_body(data)
            if limited:
                raise RateLimitError(f"MiniMax image base_resp rate limit (retry after {retry}s)", retry_after=retry)
            import base64
            b64 = data["data"]["image_base64"][0]
            return base64.b64decode(b64)

    async def text_to_speech(self, text: str, **kwargs) -> bytes:
        """MiniMax Speech-02 语音合成, 返回 MP3 二进制"""
        model = kwargs.pop("model", self.config.speech_model or "speech-02")
        voice = kwargs.pop("voice", "default")
        async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
            resp = await client.post(
                self._endpoint("/v1/text_to_speech"),
                headers=self._headers(),
                json={
                    "model": model,
                    "text": text,
                    "voice_setting": {
                        "voice_id": voice,
                        "speed": kwargs.get("speed", 1.0),
                        "emotion": kwargs.get("emotion", "neutral"),
                    },
                    "audio_setting": {"format": "mp3"},
                },
            )
            limited, retry = _parse_rate_limit_headers(resp.headers)
            if limited:
                raise RateLimitError(f"MiniMax TTS rate limited (retry after {retry}s)", retry_after=retry)
            if resp.status_code == 429:
                raise RateLimitError("MiniMax TTS 429 Too Many Requests", retry_after=retry or 60.0)
            resp.raise_for_status()
            data = resp.json()

            # body-level 限流检测 (在解包 base_resp 之前)
            limited, retry = _check_rate_limit_in_body(data)
            if limited:
                raise RateLimitError(f"MiniMax TTS base_resp rate limit (retry after {retry}s)", retry_after=retry)

            # 新包装格式: {"base_resp": {...}}
            if "base_resp" in data and isinstance(data["base_resp"], dict):
                data = data["base_resp"]

            # MiniMax TTS v2: audio in base64 at top level or in data.audio
            import base64

            # 新格式: {"data": {"audio": "base64..."}}
            if "data" in data and isinstance(data["data"], dict):
                audio_b64 = data["data"].get("audio")
                if audio_b64:
                    return base64.b64decode(audio_b64)

            # 旧格式: URL 下载
            audio_url = data.get("audio_file") or data.get("audio_url")
            if audio_url:
                async with httpx.AsyncClient(trust_env=False) as c2:
                    ar = await c2.get(audio_url)
                    ar.raise_for_status()
                    return ar.content

            # 兜底: 尝试将整个 response content 当作音频
            if resp.content and len(resp.content) > 100:
                return resp.content

            import logging
            logging.getLogger(__name__).warning(
                f"MiniMax TTS unexpected response keys: {list(data.keys()) if isinstance(data, dict) else type(data)}"
            )
            raise RuntimeError("Unexpected TTS response format")
