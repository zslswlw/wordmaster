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
    existing = db.query(ApiConfig).filter(ApiConfig.provider == data.provider).first()
    if existing:
        if data.api_key:
            existing.api_key_encrypted = encrypt_secret(data.api_key)
        existing.api_base = data.api_base
        existing.text_model = data.text_model
        existing.image_model = data.image_model
        existing.speech_model = data.speech_model
        existing.is_enabled = data.is_enabled
        db.commit()
        return {"id": existing.id, "message": "配置已更新"}

    if not data.api_key:
        raise HTTPException(400, "首次配置需要填写 API Key")
    model_data = data.model_dump()
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
    model_data = data.model_dump()
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
    api_key = data.api_key
    if not api_key:
        stored = db.query(ApiConfig).filter(ApiConfig.provider == data.provider).first()
        if stored:
            api_key = decrypt_secret(stored.api_key_encrypted)
    if not api_key:
        return {"success": False, "message": "请先保存 API Key"}
    config = ProviderConfig(
        api_key=api_key, api_base=data.api_base,
        text_model=data.text_model, image_model=data.image_model or "",
        speech_model=data.speech_model or "",
    )
    try:
        if data.provider == "deepseek":
            provider = DeepSeekProvider(config)
        elif data.provider == "minimax":
            provider = MiniMaxProvider(config)
        else:
            return {"success": False, "message": f"未知 provider: {data.provider}"}

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
