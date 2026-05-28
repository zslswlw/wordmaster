"""DeepSeek Provider — OpenAI 兼容接口"""
import httpx
from .base import BaseProvider, ProviderConfig


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
