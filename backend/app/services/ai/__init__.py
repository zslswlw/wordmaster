"""AI 服务门面 — 统一管理 DeepSeek + MiniMax Provider"""
import json
import logging
import os
import re
import time
from typing import Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    ValidationError,
    field_validator,
)
from sqlalchemy.orm import Session

from .base import (
    BaseProvider,
    ConfigurationError,
    ContentRejectedError,
    ProviderConfig,
    ProviderError,
    RateLimitError,
)
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
    memory_anchor: str = Field(min_length=1, max_length=80)
    scene_summary: str = Field(min_length=1, max_length=120)
    image_prompt: str = Field(min_length=20, max_length=800)
    narration_text: str = Field(min_length=1, max_length=64)
    scores: MemoryQualityScores
    approved: bool
    _generation_model: Optional[str] = PrivateAttr(default=None)
    _fallback_errors: list[dict] = PrivateAttr(default_factory=list)

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

    @field_validator("memory_anchor")
    @classmethod
    def keep_memory_anchor_short(cls, value: str) -> str:
        if len(re.findall(r"[\u3400-\u9fff]", value)) > 45:
            raise ValueError("memory_anchor exceeds 45 Chinese characters")
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


class MemoryBundleBatchItem(MemoryBundleCandidate):
    job_id: str


class ErrorPatternCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = Field(min_length=1, max_length=48)
    name: str = Field(min_length=1, max_length=40)
    words: list[str] = Field(min_length=1, max_length=50)
    explanation: str = Field(min_length=1, max_length=300)
    practice: list[str] = Field(default_factory=list, max_length=12)


class ErrorAnalysisCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patterns: list[ErrorPatternCandidate] = Field(default_factory=list, max_length=12)
    summary: str = Field(min_length=1, max_length=400)


class InteractiveAiGenerationError(RuntimeError):
    """Safe, user-facing failure for synchronous learning-report features."""

    def __init__(self, code: str, public_message: str):
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message


class AiService:
    """AI 服务门面"""

    def __init__(self, db: Session):
        self.db = db
        self._deepseek: Optional[DeepSeekProvider] = None
        self._minimax: Optional[MiniMaxProvider] = None
        self.batch_fallback_error: Optional[dict] = None
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

    def _text_providers(self) -> list[BaseProvider]:
        providers = []
        for provider in (self.minimax, self.deepseek):
            if provider is not None and provider not in providers:
                providers.append(provider)
        return providers

    @staticmethod
    def _provider_identity(provider: BaseProvider) -> tuple[str, str]:
        name = "minimax" if isinstance(provider, MiniMaxProvider) else "deepseek"
        return name, provider.config.text_model or name

    @staticmethod
    def _interactive_text_options(
        provider: BaseProvider,
        *,
        temperature: float,
        token_limit: int,
    ) -> dict:
        if isinstance(provider, MiniMaxProvider):
            return {
                "temperature": temperature,
                "max_completion_tokens": token_limit,
                "thinking": {"type": "disabled"},
                "queue_timeout": 15,
            }
        return {"temperature": temperature, "max_tokens": token_limit}

    async def generate_memory_candidate(
        self,
        word: models.Word,
        *,
        feedback_context: str = "",
        validation_feedback: str = "",
        prefer_deepseek: bool = False,
    ) -> MemoryBundleCandidate:
        """Generate one strictly validated memory plan; callers own retry policy."""

        provider_order = (
            (self.deepseek, self.minimax)
            if prefer_deepseek
            else (self.minimax, self.deepseek)
        )
        providers = [
            provider
            for provider in provider_order
            if provider is not None
        ]
        if not providers:
            raise ConfigurationError(
                "MiniMax/DeepSeek 文本模型未配置",
                code="not_configured",
            )
        last_error = None
        fallback_errors = []
        for provider in providers:
            request_started = time.perf_counter()
            try:
                candidate = await self._candidate_from_provider(
                    provider,
                    word,
                    feedback_context=feedback_context,
                    validation_feedback=validation_feedback,
                )
                candidate._fallback_errors = fallback_errors
                return candidate
            # Provider/network failures may use the configured fallback. Schema
            # and quality failures belong to the content and must be repaired,
            # not hidden by silently switching models.
            except ContentRejectedError:
                raise
            except (ProviderError, RateLimitError, RuntimeError) as exc:
                last_error = exc
                fallback_errors.append({
                    "provider": (
                        "minimax" if isinstance(provider, MiniMaxProvider) else "deepseek"
                    ),
                    "model": provider.config.text_model,
                    "duration_ms": max(
                        0,
                        round((time.perf_counter() - request_started) * 1000),
                    ),
                    "error_code": getattr(exc, "code", None) or exc.__class__.__name__,
                })
        raise last_error or ProviderError("文字模型调用失败")

    async def _candidate_from_provider(
        self,
        provider: BaseProvider,
        word: models.Word,
        *,
        feedback_context: str = "",
        validation_feedback: str = "",
    ) -> MemoryBundleCandidate:
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
            validation_feedback=(
                f"上一次输出未通过校验：{validation_feedback}。只修正这些问题后重新输出完整 JSON。"
                if validation_feedback
                else ""
            ),
        )
        messages = [
            {
                "role": "system",
                "content": "你是严谨的词汇记忆内容编辑。这是短小的结构化编辑任务，不需要深度推理，只输出符合 Schema 的 JSON。",
            },
            {"role": "user", "content": prompt},
        ]
        options = {"temperature": 0.35}
        if isinstance(provider, MiniMaxProvider):
            options.update({
                "max_completion_tokens": 1200,
                "thinking": {"type": "disabled"},
            })
        else:
            options["max_tokens"] = 1200
        data = await provider.chat_json(messages, **options)
        candidate = MemoryBundleCandidate.model_validate(data)
        if not candidate.quality_passed():
            raise ValueError("AI 记忆方案质量评分未达到 4/5")
        candidate._generation_model = provider.config.text_model
        return candidate

    async def generate_memory_candidates(
        self,
        entries: list[tuple[str, models.Word]],
        *,
        prefer_deepseek: bool = False,
    ) -> tuple[dict[str, MemoryBundleCandidate], dict[str, str]]:
        """Generate up to five initial bundles in one MiniMax request."""

        if not entries:
            return {}, {}
        if len(entries) > 5:
            raise ValueError("Memory bundle batch cannot exceed five items")
        provider = None if prefer_deepseek else self.minimax
        if not provider:
            candidates = {}
            errors = {}
            for job_id, word in entries:
                try:
                    candidates[job_id] = await self.generate_memory_candidate(
                        word,
                        prefer_deepseek=prefer_deepseek,
                    )
                except Exception as exc:
                    errors[job_id] = str(exc)[:600]
            return candidates, errors

        items = []
        for job_id, word in entries:
            normalized = MeaningNormalizer.normalize(word.meaning)
            items.append({
                "job_id": job_id,
                "word": word.word,
                "phonetic": word.phonetic or "",
                "normalized_pos": normalized.normalized_pos or "无法确定",
                "primary_meaning": normalized.primary_meaning,
            })
        messages = [
            {
                "role": "system",
                "content": "你是严谨的词汇记忆内容编辑。直接输出符合 Schema 的 JSON，不进行长推理。",
            },
            {
                "role": "user",
                "content": prompts.MEMORY_BUNDLE_BATCH.format(
                    items_json=json.dumps(items, ensure_ascii=False),
                ),
            },
        ]
        request_started = time.perf_counter()
        try:
            data = await provider.chat_json(
                messages,
                temperature=0.35,
                max_completion_tokens=max(2400, len(entries) * 900),
                thinking={"type": "disabled"},
            )
        except ContentRejectedError:
            raise
        except (ProviderError, RateLimitError, RuntimeError, TypeError, ValueError) as exc:
            if not self.deepseek:
                raise
            self.batch_fallback_error = {
                "provider": "minimax",
                "model": provider.config.text_model or "MiniMax-M3",
                "duration_ms": max(0, round((time.perf_counter() - request_started) * 1000)),
                "error_code": getattr(exc, "code", None) or exc.__class__.__name__,
            }
            candidates = {}
            errors = {}
            for job_id, word in entries:
                try:
                    candidates[job_id] = await self._candidate_from_provider(
                        self.deepseek,
                        word,
                    )
                except Exception as exc:
                    errors[job_id] = str(exc)[:600]
            return candidates, errors
        expected = {job_id for job_id, _word in entries}
        seen: set[str] = set()
        candidates: dict[str, MemoryBundleCandidate] = {}
        errors: dict[str, str] = {}
        if not isinstance(data, dict) or set(data) != {"items"}:
            message = "批量响应顶层必须只包含 items"
            return {}, {job_id: message for job_id in expected}
        raw_items = data.get("items")
        if not isinstance(raw_items, list):
            message = "批量响应 items 必须是数组"
            return {}, {job_id: message for job_id in expected}
        for raw_item in raw_items:
            raw_job_id = raw_item.get("job_id") if isinstance(raw_item, dict) else None
            if raw_job_id not in expected or raw_job_id in seen:
                continue
            seen.add(raw_job_id)
            try:
                item = MemoryBundleBatchItem.model_validate(raw_item)
            except (ValueError, TypeError) as exc:
                errors[raw_job_id] = str(exc)[:600]
                continue
            if item.job_id != raw_job_id:
                errors[raw_job_id] = "批量响应任务标识不一致"
                continue
            if not item.quality_passed():
                errors[item.job_id] = "AI 记忆方案质量评分未达到 4/5"
                continue
            item._generation_model = provider.config.text_model
            candidates[item.job_id] = item
        for missing in expected - seen:
            errors[missing] = "批量响应缺少对应项目"
        return candidates, errors

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
        """Generate and validate an actionable spelling-error report."""
        if not self.flags.error_analysis_enabled:
            return {"patterns": [], "summary": "", "status": "disabled"}

        providers = self._text_providers()
        if not providers:
            raise InteractiveAiGenerationError(
                "ai_not_configured",
                "AI 分析服务尚未配置，请联系管理员",
            )

        submitted_words = {
            str(item.get("correct") or item.get("word") or "").strip().lower():
            str(item.get("correct") or item.get("word") or "").strip()
            for item in errors
            if str(item.get("correct") or item.get("word") or "").strip()
        }
        errors_json = json.dumps(errors, ensure_ascii=False, indent=2)
        base_prompt = prompts.ANALYZE_ERRORS.format(errors_json=errors_json)
        output_failures = 0

        for provider in providers:
            provider_name, model = self._provider_identity(provider)
            validation_feedback = ""
            for attempt in range(2):
                prompt = base_prompt
                if validation_feedback:
                    prompt += (
                        "\n\n上一版输出未通过校验："
                        f"{validation_feedback}。请重新输出完整 JSON，不要解释。"
                    )
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "你是严谨的英语拼写错误分析员。这是简短的结构化编辑任务，"
                            "不需要展开推理，只输出符合要求的 JSON。"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ]
                try:
                    data = await provider.chat_json(
                        messages,
                        **self._interactive_text_options(
                            provider,
                            temperature=0.25 if attempt else 0.35,
                            token_limit=1800,
                        ),
                    )
                    candidate = ErrorAnalysisCandidate.model_validate(data)
                    for pattern in candidate.patterns:
                        normalized_words = []
                        for word in pattern.words:
                            source_word = submitted_words.get(word.strip().lower())
                            if source_word is None:
                                raise ValueError(f"分析引用了未提交的单词：{word}")
                            if source_word not in normalized_words:
                                normalized_words.append(source_word)
                        pattern.words = normalized_words
                    result = candidate.model_dump()
                    result.update({
                        "status": "ready",
                        "provider": provider_name,
                        "model": model,
                    })
                    return result
                except (ValidationError, ValueError, TypeError, KeyError, RuntimeError) as exc:
                    output_failures += 1
                    validation_feedback = str(exc)[:300]
                    logger.warning(
                        "Error analysis output rejected from %s/%s (attempt %s): %s",
                        provider_name,
                        model,
                        attempt + 1,
                        exc,
                    )
                except (ProviderError, RateLimitError) as exc:
                    logger.warning(
                        "Error analysis provider failed for %s/%s: %s",
                        provider_name,
                        model,
                        exc,
                    )
                    break
                except Exception as exc:
                    logger.exception(
                        "Unexpected error-analysis provider failure for %s/%s",
                        provider_name,
                        model,
                    )
                    break

        if output_failures:
            raise InteractiveAiGenerationError(
                "invalid_ai_output",
                "AI 返回的分析格式异常，请稍后重试",
            )
        raise InteractiveAiGenerationError(
            "ai_provider_unavailable",
            "AI 分析服务暂时不可用，请稍后重试",
        )

    # ========== 微故事 ==========

    async def generate_story(self, words: list[str]) -> str:
        """Generate a short story and verify that every target word is used."""
        if not self.flags.story_enabled:
            return ""
        providers = self._text_providers()
        if not providers:
            raise InteractiveAiGenerationError(
                "ai_not_configured",
                "微故事服务尚未配置，请联系管理员",
            )

        unique_words = list(dict.fromkeys(word.strip() for word in words if word.strip()))
        base_prompt = prompts.GENERATE_STORY.format(words=", ".join(unique_words))
        output_failures = 0

        for provider in providers:
            provider_name, model = self._provider_identity(provider)
            validation_feedback = ""
            for attempt in range(2):
                prompt = base_prompt
                if validation_feedback:
                    prompt += (
                        "\n\nThe previous draft failed validation: "
                        f"{validation_feedback}. Return a complete replacement story only."
                    )
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "You are a concise educational story editor. This is a short writing task; "
                            "do not include reasoning, a title, Markdown, or explanations."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ]
                try:
                    story = await provider.chat(
                        messages,
                        **self._interactive_text_options(
                            provider,
                            temperature=0.55 if attempt else 0.8,
                            token_limit=600,
                        ),
                    )
                    story = self._validate_story(story, unique_words)
                    logger.info("Story generated by %s/%s", provider_name, model)
                    return story
                except (ValueError, TypeError, KeyError, RuntimeError) as exc:
                    output_failures += 1
                    validation_feedback = str(exc)[:300]
                    logger.warning(
                        "Story output rejected from %s/%s (attempt %s): %s",
                        provider_name,
                        model,
                        attempt + 1,
                        exc,
                    )
                except (ProviderError, RateLimitError) as exc:
                    logger.warning(
                        "Story provider failed for %s/%s: %s",
                        provider_name,
                        model,
                        exc,
                    )
                    break
                except Exception:
                    logger.exception(
                        "Unexpected story provider failure for %s/%s",
                        provider_name,
                        model,
                    )
                    break

        if output_failures:
            raise InteractiveAiGenerationError(
                "invalid_ai_output",
                "AI 生成的故事不完整，请稍后重试",
            )
        raise InteractiveAiGenerationError(
            "ai_provider_unavailable",
            "微故事服务暂时不可用，请稍后重试",
        )

    @staticmethod
    def _validate_story(story: str, words: list[str]) -> str:
        if not isinstance(story, str):
            raise TypeError("story must be text")
        cleaned = re.sub(r"<think>[\s\S]*?</think>", "", story, flags=re.IGNORECASE).strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(
                lines[1:-1] if lines and lines[-1].strip() == "```" else lines[1:]
            ).strip()
        token_count = len(re.findall(r"[A-Za-z]+(?:['-][A-Za-z]+)*", cleaned))
        if token_count < 40 or token_count > 140:
            raise ValueError(f"story length must be 40-140 English words, got {token_count}")
        missing = [
            word
            for word in words
            if not re.search(
                rf"(?<![A-Za-z]){re.escape(word)}(?![A-Za-z])",
                cleaned,
                flags=re.IGNORECASE,
            )
        ]
        if missing:
            raise ValueError(f"missing target words: {', '.join(missing)}")
        return cleaned

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
