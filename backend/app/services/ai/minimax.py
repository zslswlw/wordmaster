"""MiniMax Provider — 文本 + 图像生成 + TTS"""
import httpx
from .base import BaseProvider, ProviderConfig


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
            resp.raise_for_status()
            data = resp.json()
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
            resp.raise_for_status()
            data = resp.json()
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
            resp.raise_for_status()
            data = resp.json()
            audio_url = data.get("audio_file") or data.get("audio_url")
            if audio_url:
                async with httpx.AsyncClient(trust_env=False) as c2:
                    ar = await c2.get(audio_url)
                    ar.raise_for_status()
                    return ar.content
            if "data" in data and "audio" in data["data"]:
                import base64
                return base64.b64decode(data["data"]["audio"])
            raise RuntimeError("Unexpected TTS response format")
