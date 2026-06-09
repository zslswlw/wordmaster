"""LLM Provider 抽象基类"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


class RateLimitError(Exception):
    """Provider 触发了速率限制 / 时间窗口用尽.
    包含 retry_after 字段 (秒), None 表示由调用方自行退避.
    """
    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.retry_after = retry_after


class ProviderError(Exception):
    """Provider 通用错误 (非速率限制类)."""


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
        import re
        text = await self.chat(messages, **kwargs)
        text = text.strip()

        # 提取 markdown 代码块
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        # 尝试提取 {...} 块 (处理模型在 JSON 前后附加文字的情况)
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            text = m.group(0)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 尝试修复截断的 JSON: 补全缺失的闭合
            fixed = text.rstrip()
            # 移除尾部不完整的键/值
            while fixed and fixed[-1] not in "}]\"":
                fixed = fixed[:-1]
            # 补全可能缺失的引号和括号
            open_braces = fixed.count("{") - fixed.count("}")
            open_brackets = fixed.count("[") - fixed.count("]")
            in_string = (fixed.count('"') % 2) != 0
            if in_string:
                fixed += '"'
            fixed += "]" * open_brackets
            fixed += "}" * open_braces
            try:
                return json.loads(fixed)
            except json.JSONDecodeError as e:
                raise RuntimeError(
                    f"JSON decode failed after repair. Original error: {e}. "
                    f"Raw text (last 200 chars): ...{text[-200:]}"
                )

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
