"""DeepSeek Provider — OpenAI 兼容接口"""
import httpx
from .base import BaseProvider, ProviderConfig, RateLimitError


class DeepSeekProvider(BaseProvider):
    """DeepSeek API (OpenAI-compatible)

    文本模型: deepseek-chat, deepseek-reasoner
    视觉模型: deepseek-v4-flash (支持图片输入)
    不支持图像生成和 TTS
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
        model = kwargs.pop("model", self.config.text_model or "deepseek-chat")
        async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
            resp = await client.post(
                self._endpoint("/v1/chat/completions"),
                headers=self._headers(),
                json={"model": model, "messages": messages, **kwargs},
            )
            # 速率限制检测
            if resp.status_code == 429:
                retry_after = resp.headers.get("retry-after")
                try:
                    retry = float(retry_after) if retry_after else 60.0
                except (ValueError, TypeError):
                    retry = 60.0
                raise RateLimitError(f"DeepSeek 429 (retry after {retry}s)", retry_after=retry)
            h = {k.lower(): v for k, v in (resp.headers.items() if resp.headers else [])}
            for k in ("x-ratelimit-remaining-requests", "x-ratelimit-remaining-tokens"):
                v = h.get(k)
                if v is not None:
                    try:
                        if float(v) <= 0:
                            raise RateLimitError(f"DeepSeek {k}=0 exhausted", retry_after=60.0)
                    except (ValueError, TypeError):
                        pass
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def chat_with_image(self, text: str, image_url: str, **kwargs) -> str:
        """视觉理解: 文本 + 图片 → 分析回复"""
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": text},
                {"type": "image_url", "image_url": {"url": image_url}},
            ],
        }]
        return await self.chat(messages, model=self.config.image_model or "deepseek-v4-flash", **kwargs)
