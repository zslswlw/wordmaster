"""用户 API 配置管理 — 管理员专属"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from ..models import get_db, ApiConfig, FeatureFlags
from ..auth import get_admin_user, get_current_user
from ..services.ai.base import ProviderConfig
from ..services.ai.deepseek import DeepSeekProvider
from ..services.ai.minimax import MiniMaxProvider
from ..services.ai.secrets import decrypt_secret, encrypt_secret
from ..admin_consistency import RevisionConflict, audit_admin_action

router = APIRouter(prefix="/api/settings", tags=["settings"])


class ApiConfigCreate(BaseModel):
    provider: str
    api_key: Optional[str] = None
    api_base: str
    text_model: str = ""
    image_model: str = ""
    speech_model: str = ""
    is_enabled: bool = True
    expected_revision: Optional[int] = None


class ApiConfigResponse(BaseModel):
    id: int
    provider: str
    has_api_key: bool
    api_base: str
    text_model: str
    image_model: str
    speech_model: str
    is_enabled: bool
    revision: int

    class Config:
        from_attributes = True


def _config_payload(config: ApiConfig) -> dict:
    return {
        "id": config.id,
        "provider": config.provider,
        "has_api_key": bool(config.api_key_encrypted),
        "api_base": config.api_base,
        "text_model": config.text_model or "",
        "image_model": config.image_model or "",
        "speech_model": config.speech_model or "",
        "is_enabled": config.is_enabled,
        "revision": config.revision,
    }


@router.get("/ai-configs")
def list_configs(db: Session = Depends(get_db), admin=Depends(get_admin_user)):
    return [_config_payload(config) for config in db.query(ApiConfig).all()]


@router.post("/ai-configs")
def create_config(
    data: ApiConfigCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    model_data = _normalized_provider_values(data)
    existing = db.query(ApiConfig).filter(
        ApiConfig.provider == model_data["provider"],
    ).first()
    if existing:
        if data.expected_revision != existing.revision:
            raise RevisionConflict(_config_payload(existing))
        return _update_existing_config(db, request, admin, existing, model_data)

    if not model_data["api_key"]:
        raise HTTPException(400, "首次配置需要填写 API Key")
    model_data["api_key_encrypted"] = encrypt_secret(model_data.pop("api_key"))
    cfg = ApiConfig(**model_data)
    db.add(cfg)
    db.flush()
    audit_admin_action(
        db,
        request,
        admin,
        action="ai_config.create",
        target_type="api_config",
        target_id=cfg.id,
        after=_config_payload(cfg),
    )
    db.commit()
    db.refresh(cfg)
    return _config_payload(cfg)


@router.put("/ai-configs/{config_id}")
def update_config(
    config_id: int,
    data: ApiConfigCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    cfg = db.query(ApiConfig).filter(ApiConfig.id == config_id).first()
    if not cfg:
        raise HTTPException(404, "配置不存在")
    if data.expected_revision != cfg.revision:
        raise RevisionConflict(_config_payload(cfg))
    model_data = _normalized_provider_values(data)
    return _update_existing_config(db, request, admin, cfg, model_data)


def _update_existing_config(
    db: Session,
    request: Request,
    admin,
    config: ApiConfig,
    values: dict,
) -> dict:
    before = _config_payload(config)
    expected_revision = config.revision
    api_key = values.pop("api_key")
    values.pop("expected_revision", None)
    if api_key:
        values["api_key_encrypted"] = encrypt_secret(api_key)
    values.pop("provider", None)
    updated = db.query(ApiConfig).filter(
        ApiConfig.id == config.id,
        ApiConfig.revision == expected_revision,
    ).update(
        {**values, "revision": ApiConfig.revision + 1},
        synchronize_session=False,
    )
    if updated != 1:
        db.rollback()
        current = db.query(ApiConfig).filter(ApiConfig.id == config.id).first()
        raise RevisionConflict(_config_payload(current) if current else {"deleted": True})
    db.expire_all()
    current = db.query(ApiConfig).filter(ApiConfig.id == config.id).first()
    after = _config_payload(current)
    if api_key:
        after["api_key_changed"] = True
    audit_admin_action(
        db,
        request,
        admin,
        action="ai_config.update",
        target_type="api_config",
        target_id=config.id,
        before=before,
        after=after,
    )
    db.commit()
    return _config_payload(current)


@router.delete("/ai-configs/{config_id}")
def delete_config(
    config_id: int,
    expected_revision: int,
    request: Request,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    cfg = db.query(ApiConfig).filter(ApiConfig.id == config_id).first()
    if not cfg:
        raise HTTPException(404, "配置不存在")
    if cfg.revision != expected_revision:
        raise RevisionConflict(_config_payload(cfg))
    before = _config_payload(cfg)
    deleted = db.query(ApiConfig).filter(
        ApiConfig.id == config_id,
        ApiConfig.revision == expected_revision,
    ).delete(synchronize_session=False)
    if deleted != 1:
        db.rollback()
        current = db.query(ApiConfig).filter(ApiConfig.id == config_id).first()
        raise RevisionConflict(_config_payload(current) if current else {"deleted": True})
    audit_admin_action(
        db,
        request,
        admin,
        action="ai_config.delete",
        target_type="api_config",
        target_id=config_id,
        before=before,
    )
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
    expected_revision: int


def _normalized_provider_values(data: ApiConfigCreate) -> dict:
    values = data.model_dump()
    values.pop("expected_revision", None)
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
        "revision": ff.revision,
    }


@router.put("/feature-flags")
def update_feature_flags(
    data: FeatureFlagsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_user),
):
    ff = _get_feature_flags(db)
    current = get_feature_flags(db=db, current_user=admin)
    if data.expected_revision != ff.revision:
        raise RevisionConflict(current)
    values = data.model_dump(exclude={"expected_revision"})
    updated = db.query(FeatureFlags).filter(
        FeatureFlags.id == ff.id,
        FeatureFlags.revision == data.expected_revision,
    ).update(
        {**values, "revision": FeatureFlags.revision + 1},
        synchronize_session=False,
    )
    if updated != 1:
        db.rollback()
        latest = _get_feature_flags(db)
        raise RevisionConflict(get_feature_flags(db=db, current_user=admin))
    db.expire_all()
    updated_flags = _get_feature_flags(db)
    after = get_feature_flags(db=db, current_user=admin)
    audit_admin_action(
        db,
        request,
        admin,
        action="feature_flags.update",
        target_type="feature_flags",
        target_id=updated_flags.id,
        before=current,
        after=after,
    )
    db.commit()
    return after
