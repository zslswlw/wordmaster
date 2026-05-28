"""AI 服务门面 — 统一管理 DeepSeek + MiniMax Provider"""
import logging
import os
from typing import Optional
from sqlalchemy.orm import Session

from .base import BaseProvider, ProviderConfig
from .deepseek import DeepSeekProvider
from .minimax import MiniMaxProvider
from . import prompts
from ... import models

logger = logging.getLogger(__name__)

IMAGES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "ai_images")


class AiService:
    """AI 服务门面"""

    def __init__(self, db: Session):
        self.db = db
        self._deepseek: Optional[DeepSeekProvider] = None
        self._minimax: Optional[MiniMaxProvider] = None

    def _get_config(self, provider: str) -> Optional[ProviderConfig]:
        cfg = self.db.query(models.ApiConfig).filter(
            models.ApiConfig.provider == provider,
            models.ApiConfig.is_enabled == True,
        ).first()
        if not cfg:
            return None
        return ProviderConfig(
            api_key=cfg.api_key_encrypted,
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

    # ========== 单词增强 ==========

    async def enrich_word(self, word_id: int) -> bool:
        """为单个单词生成 AI 增强内容, 存入 DB"""
        word = self.db.query(models.Word).filter(models.Word.id == word_id).first()
        if not word:
            return False
        if not self.deepseek:
            logger.warning("DeepSeek not configured, skipping enrichment")
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
            data = await self.deepseek.chat_json(messages, temperature=0.7, max_tokens=1024)
        except Exception as e:
            logger.error(f"DeepSeek enrichment failed for '{word.word}': {e}")
            return False

        word.example_l1 = data.get("example_l1")
        word.example_l2 = data.get("example_l2")
        word.example_l3 = data.get("example_l3")
        word.image_prompt = data.get("image_prompt")
        word.mnemonic = data.get("mnemonic")
        word.etymology = data.get("etymology")
        word.word_family = str(data.get("word_family")) if data.get("word_family") else None
        word.synonyms = str(data.get("synonyms")) if data.get("synonyms") else None
        word.enriched = True
        self.db.commit()
        logger.info(f"Enriched word: {word.word}")
        return True

    async def enrich_bank(self, bank_id: int, progress_callback=None) -> dict:
        """批量增强整个词库"""
        words = self.db.query(models.Word).filter(models.Word.bank_id == bank_id).all()
        total = len(words)
        success = 0
        failed = 0
        for i, word in enumerate(words):
            if word.enriched:
                success += 1
                if progress_callback:
                    progress_callback(i + 1, total)
                continue
            ok = await self.enrich_word(word.id)
            if ok:
                success += 1
            else:
                failed += 1
            if progress_callback:
                progress_callback(i + 1, total)
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
        """为单词生成视觉词卡, 返回本地路径"""
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

        try:
            img_data = await self.minimax.generate_image(word.image_prompt)
            with open(filepath, "wb") as f:
                f.write(img_data)
            word.image_url = filepath
            self.db.commit()
            logger.info(f"Generated image for: {word.word}")
            return filepath
        except Exception as e:
            logger.error(f"Image generation failed for '{word.word}': {e}")
            return None

    # ========== 错题分析 ==========

    async def analyze_errors(self, errors: list[dict]) -> dict:
        """分析错题模式"""
        if not self.deepseek:
            return {"patterns": [], "summary": "AI 未配置"}
        try:
            import json
            errors_json = json.dumps(errors, ensure_ascii=False, indent=2)
            prompt = prompts.ANALYZE_ERRORS.format(errors_json=errors_json)
            messages = [
                {"role": "system", "content": "You are an English spelling analyst. Always return valid JSON."},
                {"role": "user", "content": prompt},
            ]
            return await self.deepseek.chat_json(messages, temperature=0.3, max_tokens=2048)
        except Exception as e:
            logger.error(f"Error analysis failed: {e}")
            return {"patterns": [], "summary": f"分析失败: {str(e)}"}

    # ========== 微故事 ==========

    async def generate_story(self, words: list[str]) -> str:
        """用错词生成微故事"""
        if not self.deepseek:
            return ""
        try:
            prompt = prompts.GENERATE_STORY.format(words=", ".join(words))
            messages = [
                {"role": "system", "content": "You are a creative writer. Return only the story text."},
                {"role": "user", "content": prompt},
            ]
            return await self.deepseek.chat(messages, temperature=0.9, max_tokens=300)
        except Exception as e:
            logger.error(f"Story generation failed: {e}")
            return ""

    # ========== 近义词辨析 ==========

    async def distinguish_words(self, word1: str, meaning1: str, word2: str, meaning2: str) -> dict:
        """辨析近义词差异"""
        if not self.deepseek:
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
            return await self.deepseek.chat_json(messages, temperature=0.5, max_tokens=1024)
        except Exception as e:
            logger.error(f"Distinguish failed: {e}")
            return {}
