"""用户 API 配置管理"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from ..models import get_db, ApiConfig
from ..services.ai.base import ProviderConfig
from ..services.ai.deepseek import DeepSeekProvider
from ..services.ai.minimax import MiniMaxProvider

router = APIRouter(prefix="/api/settings", tags=["settings"])


class ApiConfigCreate(BaseModel):
    provider: str
    api_key: str
    api_base: str
    text_model: str = ""
    image_model: str = ""
    speech_model: str = ""
    is_enabled: bool = True


class ApiConfigResponse(BaseModel):
    id: int
    provider: str
    api_key_masked: str
    api_base: str
    text_model: str
    image_model: str
    speech_model: str
    is_enabled: bool

    class Config:
        from_attributes = True


@router.get("/ai-configs")
def list_configs(db: Session = Depends(get_db)):
    configs = db.query(ApiConfig).all()
    return [{
        "id": c.id, "provider": c.provider,
        "api_key_masked": c.api_key_encrypted[:4] + "****" + c.api_key_encrypted[-4:] if len(c.api_key_encrypted) > 8 else "****",
        "api_base": c.api_base, "text_model": c.text_model or "",
        "image_model": c.image_model or "", "speech_model": c.speech_model or "",
        "is_enabled": c.is_enabled,
    } for c in configs]


@router.post("/ai-configs")
def create_config(data: ApiConfigCreate, db: Session = Depends(get_db)):
    existing = db.query(ApiConfig).filter(ApiConfig.provider == data.provider).first()
    if existing:
        existing.api_key_encrypted = data.api_key
        existing.api_base = data.api_base
        existing.text_model = data.text_model
        existing.image_model = data.image_model
        existing.speech_model = data.speech_model
        existing.is_enabled = data.is_enabled
        db.commit()
        return {"id": existing.id, "message": "配置已更新"}

    model_data = data.model_dump()
    model_data["api_key_encrypted"] = model_data.pop("api_key")
    cfg = ApiConfig(**model_data)
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return {"id": cfg.id, "message": "配置已创建"}


@router.put("/ai-configs/{config_id}")
def update_config(config_id: int, data: ApiConfigCreate, db: Session = Depends(get_db)):
    cfg = db.query(ApiConfig).filter(ApiConfig.id == config_id).first()
    if not cfg:
        raise HTTPException(404, "配置不存在")
    model_data = data.model_dump()
    model_data["api_key_encrypted"] = model_data.pop("api_key")
    for k, v in model_data.items():
        setattr(cfg, k, v)
    db.commit()
    return {"message": "配置已更新"}


@router.delete("/ai-configs/{config_id}")
def delete_config(config_id: int, db: Session = Depends(get_db)):
    cfg = db.query(ApiConfig).filter(ApiConfig.id == config_id).first()
    if not cfg:
        raise HTTPException(404, "配置不存在")
    db.delete(cfg)
    db.commit()
    return {"message": "配置已删除"}


@router.post("/ai-configs/test")
async def test_connection(data: ApiConfigCreate):
    """测试 API 连接"""
    config = ProviderConfig(
        api_key=data.api_key, api_base=data.api_base,
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
