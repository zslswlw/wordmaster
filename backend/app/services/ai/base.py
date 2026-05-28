"""LLM Provider 抽象基类"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ProviderConfig:
    api_key: str
    api_base: str
    text_model: str = ""
    image_model: str = ""
    speech_model: str = ""


class BaseProvider(ABC):
    """AI Provider 抽象基类 — DeepSeek / MiniMax 等统一接口"""

    def __init__(self, config: ProviderConfig):
        self.config = config

    @abstractmethod
    async def chat(self, messages: list[dict], **kwargs) -> str:
        """文本对话, 返回回复内容"""

    async def chat_json(self, messages: list[dict], **kwargs) -> dict:
        """文本对话并解析 JSON 返回"""
        import json
        text = await self.chat(messages, **kwargs)
        # 尝试提取 JSON 块
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        return json.loads(text)

    async def generate_image(self, prompt: str, **kwargs) -> bytes:
        """图像生成, 返回图片二进制数据。不支持则 raise NotImplementedError"""
        raise NotImplementedError(f"{self.__class__.__name__} does not support image generation")

    async def text_to_speech(self, text: str, **kwargs) -> bytes:
        """语音合成, 返回音频二进制数据。不支持则 raise NotImplementedError"""
        raise NotImplementedError(f"{self.__class__.__name__} does not support TTS")

    async def test_connection(self) -> tuple[bool, str]:
        """测试 API 连接是否正常, 返回 (成功, 信息)"""
        try:
            await self.chat([{"role": "user", "content": "hi"}], max_tokens=5)
            return True, "连接正常"
        except Exception as e:
            return False, str(e)
