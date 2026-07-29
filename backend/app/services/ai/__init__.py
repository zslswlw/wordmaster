"""AI 服务门面 — 统一管理 DeepSeek + MiniMax Provider"""
import logging
import os
import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, field_validator
from sqlalchemy.orm import Session

from .base import BaseProvider, ProviderConfig, ProviderError, RateLimitError
from .deepseek import DeepSeekProvider
from .minimax import MiniMaxProvider
from .secrets import decrypt_secret
from . import prompts
from ... import models
from ..learning_content import MeaningNormalizer

logger = logging.getLogger(__name__)

IMAGES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "ai_images")
CONTEXT_AUDIO_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "frontend", "public", "audio_context")


class MemoryQualityScores(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meaning_consistency: int = Field(ge=1, le=5)
    association_naturalness: int = Field(ge=1, le=5)
    visual_clarity: int = Field(ge=1, le=5)
    distinctiveness: int = Field(ge=1, le=5)


class MemoryBundleCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    normalized_pos: Optional[str] = None
    primary_meaning: str = Field(min_length=1, max_length=48)
    strategy: Literal["direct", "metaphor", "natural_homophone"]
    memory_anchor: str = Field(min_length=1, max_length=45)
    scene_summary: str = Field(min_length=1, max_length=120)
    image_prompt: str = Field(min_length=20, max_length=800)
    narration_text: str = Field(min_length=1, max_length=64)
    scores: MemoryQualityScores
    approved: bool
    _generation_model: Optional[str] = PrivateAttr(default=None)

    @field_validator("primary_meaning")
    @classmethod
    def keep_primary_meaning_short(cls, value: str) -> str:
        if len(re.findall(r"[\u3400-\u9fff]", value)) > 24:
            raise ValueError("primary_meaning exceeds 24 Chinese characters")
        return value

    @field_validator("image_prompt")
    @classmethod
    def require_english_image_prompt(cls, value: str) -> str:
        if re.search(r"[\u3400-\u9fff]", value):
            raise ValueError("image_prompt must be English")
        return value

    @field_validator("narration_text")
    @classmethod
    def reject_raw_pos_abbreviations(cls, value: str) -> str:
        lowered = value.lower()
        if any(token in lowered for token in ("vt.", "vi.", "adj.", "adv.", "prep.")):
            raise ValueError("narration_text contains raw part-of-speech abbreviation")
        if len(re.findall(r"[\u3400-\u9fff]", value)) > 32:
            raise ValueError("narration_text exceeds 32 Chinese characters")
        return value

    def quality_passed(self) -> bool:
        return self.approved and min(
            self.scores.meaning_consistency,
            self.scores.association_naturalness,
            self.scores.visual_clarity,
            self.scores.distinctiveness,
        ) >= 4

    @property
    def generation_model(self) -> Optional[str]:
        return self._generation_model


class AiService:
    """AI 服务门面"""

    def __init__(self, db: Session):
        self.db = db
        self._deepseek: Optional[DeepSeekProvider] = None
        self._minimax: Optional[MiniMaxProvider] = None
        ff = db.query(models.FeatureFlags).first()
        self.flags = ff or models.FeatureFlags(id=1)

    def _get_config(self, provider: str) -> Optional[ProviderConfig]:
        cfg = self.db.query(models.ApiConfig).filter(
            models.ApiConfig.provider == provider,
            models.ApiConfig.is_enabled == True,
        ).first()
        if not cfg:
            return None
        return ProviderConfig(
            api_key=decrypt_secret(cfg.api_key_encrypted),
            api_base=cfg.api_base,
            text_model=cfg.text_model or "",
            image_model=cfg.image_model or "",
            speech_model=cfg.speech_model or "",
        )

    @property
    def deepseek(self) -> Optional[DeepSeekProvider]:
        if self._deepseek is None:
            cfg = self._get_config("deepseek")
            self._deepseek = DeepSeekProvider(cfg) if cfg else None
        return self._deepseek

    @property
    def minimax(self) -> Optional[MiniMaxProvider]:
        if self._minimax is None:
            cfg = self._get_config("minimax")
            self._minimax = MiniMaxProvider(cfg) if cfg else None
        return self._minimax

    @property
    def text_provider(self) -> Optional[BaseProvider]:
        return self.minimax or self.deepseek

    async def generate_memory_candidate(
        self,
        word: models.Word,
        *,
        feedback_context: str = "",
    ) -> MemoryBundleCandidate:
        """Generate one strictly validated memory plan; callers own retry policy."""

        providers = [
            provider
            for provider in (self.minimax, self.deepseek)
            if provider is not None
        ]
        if not providers:
            raise ProviderError(
                "MiniMax/DeepSeek 文本模型未配置",
                code="not_configured",
            )
        normalized = MeaningNormalizer.normalize(word.meaning)
        prompt = prompts.MEMORY_BUNDLE.format(
            word=word.word,
            phonetic=word.phonetic or "",
            normalized_pos=normalized.normalized_pos or "无法确定",
            primary_meaning=normalized.primary_meaning,
            feedback_context=(
                f"上一版反馈：{feedback_context}。请针对反馈重做，不能只换措辞。"
                if feedback_context
                else ""
            ),
        )
        messages = [
            {
                "role": "system",
                "content": "你是严谨的词汇记忆内容编辑，只输出符合指定 Schema 的 JSON。",
            },
            {"role": "user", "content": prompt},
        ]
        data = None
        selected_provider = None
        last_provider_error = None
        for provider in providers:
            try:
                data = await provider.chat_json(
                    messages,
                    temperature=0.45,
                    max_tokens=1600,
                )
                selected_provider = provider
                break
            except (ProviderError, RateLimitError) as exc:
                last_provider_error = exc
        if data is None:
            raise last_provider_error or ProviderError("文字模型调用失败")
        candidate = MemoryBundleCandidate.model_validate(data)
        candidate._generation_model = (
            selected_provider.config.text_model
            if selected_provider
            else None
        )
        if not candidate.quality_passed():
            raise ValueError("AI 记忆方案质量评分未达到 4/5")
        return candidate

    # ========== 单词增强 ==========

    async def enrich_word(self, word_id: int) -> bool:
        """为单个单词生成 AI 增强内容, 存入 DB.
        RateLimitError 向上抛, 由 pipeline 统一处理等待/重试.
        """
        word = self.db.query(models.Word).filter(models.Word.id == word_id).first()
        if not word:
            return False
        if not self.text_provider:
            logger.warning("No text provider configured, skipping enrichment")
            return False

        try:
            prompt = prompts.ENRICH_WORD.format(
                word=word.word,
                meaning=word.meaning or "",
                phonetic=word.phonetic or "",
                first_letter=word.word[0] if word.word else "?",
                length=len(word.word) if word.word else 0,
            )
            messages = [
                {"role": "system", "content": "You are a vocabulary tutor. Return exactly the JSON requested, no extra text."},
                {"role": "user", "content": prompt},
            ]
            data = await self.text_provider.chat_json(messages, temperature=0.7, max_tokens=4096)
        except RateLimitError:
            raise  # 让 pipeline 知道
        except Exception as e:
            logger.error(f"DeepSeek enrichment failed for '{word.word}': {e}")
            return False

        if self.flags.example_enabled:
            word.example_l1 = data.get("example_l1")
            word.example_l2 = data.get("example_l2")
            word.example_l3 = data.get("example_l3")
        if self.flags.image_enabled:
            word.image_prompt = data.get("image_prompt")
        if self.flags.mnemonic_enabled:
            word.mnemonic = data.get("mnemonic")
        word.etymology = data.get("etymology")
        word.word_family = str(data.get("word_family")) if data.get("word_family") else None
        word.synonyms = str(data.get("synonyms")) if data.get("synonyms") else None
        word.enriched = True
        self.db.commit()
        logger.info(f"Enriched word: {word.word}")

        # 生成语境发音 (MiniMax TTS 朗读 example_l2)
        # 限流错误向上抛, 由 pipeline 等待下个窗口; 其他错误忽略 (不阻塞 enrich)
        if self.flags.example_enabled and word.example_l2 and self.minimax:
            try:
                await self._generate_context_audio(word)
            except RateLimitError:
                raise  # 限流必须向外传播, 触发等待
            except Exception as e:
                logger.warning(f"Context audio failed for '{word.word}': {e}")

        return True

    async def enrich_bank(self, bank_id: int, progress_callback=None) -> dict:
        """批量增强整个词库"""
        words = self.db.query(models.Word).filter(models.Word.bank_id == bank_id).all()
        unenriched = [w for w in words if not w.enriched]
        skipped = len(words) - len(unenriched)
        total = len(words)
        success = skipped
        failed = 0
        done = 0
        for word in unenriched:
            ok = await self.enrich_word(word.id)
            if ok:
                success += 1
            else:
                failed += 1
            done += 1
            if progress_callback:
                progress_callback(done, len(unenriched))
        return {"total": total, "success": success, "failed": failed}

    async def generate_bank_images(self, bank_id: int, progress_callback=None) -> dict:
        """批量生成整个词库的视觉词卡"""
        words = self.db.query(models.Word).filter(
            models.Word.bank_id == bank_id,
            models.Word.enriched == True,
            models.Word.image_prompt != None,
            models.Word.image_prompt != "",
        ).all()
        total = len(words)
        success = 0
        failed = 0
        skipped = 0
        for i, word in enumerate(words):
            if word.image_url and os.path.exists(word.image_url):
                skipped += 1
                if progress_callback:
                    progress_callback(i + 1, total)
                continue
            path = await self.generate_word_image(word.id)
            if path:
                success += 1
            else:
                failed += 1
            if progress_callback:
                progress_callback(i + 1, total)
        return {"total": total, "success": success, "failed": failed, "skipped": skipped}

    async def generate_word_image(self, word_id: int) -> Optional[str]:
        """为单词生成视觉词卡, 返回本地路径.
        遇到 RateLimitError 时向上抛, 由 pipeline 统一处理等待/重试.
        """
        if not self.flags.image_enabled:
            return None
        word = self.db.query(models.Word).filter(models.Word.id == word_id).first()
        if not word or not word.image_prompt:
            return None
        if not self.minimax:
            logger.warning("MiniMax not configured")
            return None

        os.makedirs(IMAGES_DIR, exist_ok=True)
        filename = f"{word.word.lower().replace(' ', '_')}.png"
        filepath = os.path.join(IMAGES_DIR, filename)
        if os.path.exists(filepath):
            word.image_url = filepath
            self.db.commit()
            return filepath

        img_data = await self.minimax.generate_image(word.image_prompt)
        with open(filepath, "wb") as f:
            f.write(img_data)
        word.image_url = filepath
        self.db.commit()
        logger.info(f"Generated image for: {word.word}")
        return filepath

    async def _generate_context_audio(self, word) -> bool:
        """为单词的例句生成 MiniMax TTS 语境发音.
        遇到 RateLimitError 时向上抛, 由 pipeline 统一处理等待/重试.
        """
        if not word.example_l2 or not self.minimax:
            return False

        os.makedirs(CONTEXT_AUDIO_DIR, exist_ok=True)
        filename = f"{word.word.lower().replace(' ', '_')}.mp3"
        filepath = os.path.join(CONTEXT_AUDIO_DIR, filename)

        if os.path.exists(filepath):
            word.context_audio = f"/audio_context/{filename}"
            self.db.commit()
            return True

        audio_data = await self.minimax.text_to_speech(
            word.example_l2, voice="default", speed=0.9
        )
        with open(filepath, "wb") as f:
            f.write(audio_data)
        word.context_audio = f"/audio_context/{filename}"
        self.db.commit()
        logger.info(f"Generated context audio for: {word.word}")
        return True

    async def generate_context_audio_batch(self, bank_id: int, progress_callback=None) -> dict:
        """批量生成词库的语境发音"""
        words = self.db.query(models.Word).filter(
            models.Word.bank_id == bank_id,
            models.Word.enriched == True,
            models.Word.example_l2 != None,
            models.Word.example_l2 != "",
        ).all()
        total = len(words)
        success = 0
        failed = 0
        skipped = 0
        for i, word in enumerate(words):
            if word.context_audio and os.path.exists(
                os.path.join(CONTEXT_AUDIO_DIR, f"{word.word.lower().replace(' ', '_')}.mp3")
            ):
                skipped += 1
            else:
                ok = await self._generate_context_audio(word)
                if ok:
                    success += 1
                else:
                    failed += 1
            if progress_callback:
                progress_callback(i + 1, total)
        return {"total": total, "success": success, "failed": failed, "skipped": skipped}

    # ========== 错题分析 ==========

    async def analyze_errors(self, errors: list[dict]) -> dict:
        """分析错题模式"""
        if not self.flags.error_analysis_enabled:
            return {"patterns": [], "summary": ""}
        if not self.text_provider:
            return {"patterns": [], "summary": "AI 未配置"}
        try:
            import json
            errors_json = json.dumps(errors, ensure_ascii=False, indent=2)
            prompt = prompts.ANALYZE_ERRORS.format(errors_json=errors_json)
            messages = [
                {"role": "system", "content": "You are an English spelling analyst. Always return valid JSON."},
                {"role": "user", "content": prompt},
            ]
            return await self.text_provider.chat_json(messages, temperature=0.3, max_tokens=2048)
        except Exception as e:
            logger.error(f"Error analysis failed: {e}")
            return {"patterns": [], "summary": f"分析失败: {str(e)}"}

    # ========== 微故事 ==========

    async def generate_story(self, words: list[str]) -> str:
        """用错词生成微故事"""
        if not self.flags.story_enabled:
            return ""
        if not self.text_provider:
            return ""
        try:
            prompt = prompts.GENERATE_STORY.format(words=", ".join(words))
            messages = [
                {"role": "system", "content": "You are a creative writer. Return only the story text."},
                {"role": "user", "content": prompt},
            ]
            return await self.text_provider.chat(messages, temperature=0.9, max_tokens=300)
        except Exception as e:
            logger.error(f"Story generation failed: {e}")
            return ""

    # ========== 近义词辨析 ==========

    async def distinguish_words(self, word1: str, meaning1: str, word2: str, meaning2: str) -> dict:
        """辨析近义词差异"""
        if not self.text_provider:
            return {}
        try:
            prompt = prompts.DISTINGUISH.format(
                word1=word1, meaning1=meaning1,
                word2=word2, meaning2=meaning2,
            )
            messages = [
                {"role": "system", "content": "You are a linguistics expert. Always return valid JSON."},
                {"role": "user", "content": prompt},
            ]
            return await self.text_provider.chat_json(messages, temperature=0.5, max_tokens=1024)
        except Exception as e:
            logger.error(f"Distinguish failed: {e}")
            return {}
