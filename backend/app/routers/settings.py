"""用户 API 配置管理 — 管理员专属"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from ..models import get_db, ApiConfig, FeatureFlags
from ..auth import get_admin_user, get_current_user
from ..services.ai.base import ProviderConfig
from ..services.ai.deepseek import DeepSeekProvider
from ..services.ai.minimax import MiniMaxProvider
from ..services.ai.secrets import decrypt_secret, encrypt_secret

router = APIRouter(prefix="/api/settings", tags=["settings"])


class ApiConfigCreate(BaseModel):
    provider: str
    api_key: Optional[str] = None
    api_base: str
    text_model: str = ""
    image_model: str = ""
    speech_model: str = ""
    is_enabled: bool = True


class ApiConfigResponse(BaseModel):
    id: int
    provider: str
    has_api_key: bool
    api_base: str
    text_model: str
    image_model: str
    speech_model: str
    is_enabled: bool

    class Config:
        from_attributes = True


@router.get("/ai-configs")
def list_configs(db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    configs = db.query(ApiConfig).all()
    return [{
        "id": c.id, "provider": c.provider,
        "has_api_key": bool(c.api_key_encrypted),
        "api_base": c.api_base, "text_model": c.text_model or "",
        "image_model": c.image_model or "", "speech_model": c.speech_model or "",
        "is_enabled": c.is_enabled,
    } for c in configs]


@router.post("/ai-configs")
def create_config(data: ApiConfigCreate, db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    model_data = _normalized_provider_values(data)
    existing = db.query(ApiConfig).filter(
        ApiConfig.provider == model_data["provider"],
    ).first()
    if existing:
        api_key = model_data.pop("api_key")
        if api_key:
            existing.api_key_encrypted = encrypt_secret(api_key)
        for key, value in model_data.items():
            if key != "provider":
                setattr(existing, key, value)
        db.commit()
        return {"id": existing.id, "message": "配置已更新"}

    if not model_data["api_key"]:
        raise HTTPException(400, "首次配置需要填写 API Key")
    model_data["api_key_encrypted"] = encrypt_secret(model_data.pop("api_key"))
    cfg = ApiConfig(**model_data)
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return {"id": cfg.id, "message": "配置已创建"}


@router.put("/ai-configs/{config_id}")
def update_config(config_id: int, data: ApiConfigCreate, db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    cfg = db.query(ApiConfig).filter(ApiConfig.id == config_id).first()
    if not cfg:
        raise HTTPException(404, "配置不存在")
    model_data = _normalized_provider_values(data)
    api_key = model_data.pop("api_key")
    if api_key:
        model_data["api_key_encrypted"] = encrypt_secret(api_key)
    for k, v in model_data.items():
        setattr(cfg, k, v)
    db.commit()
    return {"message": "配置已更新"}


@router.delete("/ai-configs/{config_id}")
def delete_config(config_id: int, db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    cfg = db.query(ApiConfig).filter(ApiConfig.id == config_id).first()
    if not cfg:
        raise HTTPException(404, "配置不存在")
    db.delete(cfg)
    db.commit()
    return {"message": "配置已删除"}


@router.post("/ai-configs/test")
async def test_connection(data: ApiConfigCreate, db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    """测试 API 连接"""
    model_data = _normalized_provider_values(data)
    api_key = model_data["api_key"]
    if not api_key:
        stored = db.query(ApiConfig).filter(
            ApiConfig.provider == model_data["provider"],
        ).first()
        if stored:
            api_key = decrypt_secret(stored.api_key_encrypted)
    if not api_key:
        return {"success": False, "message": "请先保存 API Key"}
    config = ProviderConfig(
        api_key=api_key,
        api_base=model_data["api_base"],
        text_model=model_data["text_model"],
        image_model=model_data["image_model"] or "",
        speech_model=model_data["speech_model"] or "",
    )
    try:
        if model_data["provider"] == "deepseek":
            provider = DeepSeekProvider(config)
        elif model_data["provider"] == "minimax":
            provider = MiniMaxProvider(config)
        else:
            return {"success": False, "message": f"未知 provider: {model_data['provider']}"}

        ok, msg = await provider.test_connection()
        return {"success": ok, "message": msg}
    except Exception as e:
        return {"success": False, "message": str(e)}


class FeatureFlagsUpdate(BaseModel):
    example_enabled: bool = True
    image_enabled: bool = True
    mnemonic_enabled: bool = True
    error_analysis_enabled: bool = True
    story_enabled: bool = False


def _normalized_provider_values(data: ApiConfigCreate) -> dict:
    values = data.model_dump()
    if values["provider"].lower() != "minimax":
        return values
    old_base = (values["api_base"] or "").rstrip("/").lower()
    if old_base in {"https://api.minimax.chat", "http://api.minimax.chat"}:
        values["api_base"] = "https://api.minimaxi.com"
    model = (values["text_model"] or "").strip()
    if not model or model.lower().startswith("minimax-m2"):
        values["text_model"] = "MiniMax-M3"
    if not values["image_model"]:
        values["image_model"] = "image-01"
    if not values["speech_model"] or values["speech_model"].lower() == "speech-02":
        values["speech_model"] = "speech-2.8-turbo"
    return values


def _get_feature_flags(db: Session) -> FeatureFlags:
    """获取或创建全局唯一的 feature_flags 行"""
    ff = db.query(FeatureFlags).first()
    if not ff:
        ff = FeatureFlags(id=1)
        db.add(ff)
        db.commit()
        db.refresh(ff)
    return ff


@router.get("/feature-flags")
def get_feature_flags(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    ff = _get_feature_flags(db)
    return {
        "example_enabled": ff.example_enabled,
        "image_enabled": ff.image_enabled,
        "mnemonic_enabled": ff.mnemonic_enabled,
        "error_analysis_enabled": ff.error_analysis_enabled,
        "story_enabled": ff.story_enabled,
    }


@router.put("/feature-flags")
def update_feature_flags(data: FeatureFlagsUpdate, db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    ff = _get_feature_flags(db)
    for k, v in data.model_dump().items():
        setattr(ff, k, v)
    db.commit()
    return {"message": "功能开关已更新"}
