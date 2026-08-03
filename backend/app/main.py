import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

ENV = os.getenv("ENV", "development")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./wordmaster.db")

if ENV == "test":
    safe_test_database = (
        DATABASE_URL == "sqlite:///:memory:"
        or (
            DATABASE_URL.startswith("sqlite:///")
            and any(marker in DATABASE_URL.lower() for marker in ("test", "/tmp/", "/private/tmp/"))
        )
    )
    if not safe_test_database:
        raise RuntimeError("Test mode requires an isolated SQLite test database")

from .clock import enable_test_clock, get_clock
from .routers import (
    admin,
    ai,
    ai_evolution,
    audio,
    auth,
    backup,
    banks,
    groups,
    review,
    settings,
    study,
)
from .admin_consistency import MaintenanceLocked, RevisionConflict, get_system_state
from .models import SessionLocal
from .services.ai.worker import media_root, start_silent_worker, stop_silent_worker
from .services.learning_content import backfill_legacy_memory

if ENV == "test":
    from .routers import testing

    initial_time = os.getenv("TEST_NOW")
    enable_test_clock(datetime.fromisoformat(initial_time) if initial_time else None)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if ENV != "test":
        web_concurrency = int(os.getenv("WEB_CONCURRENCY", "1"))
        if web_concurrency != 1 and os.getenv("AI_WORKER_ENABLED", "true").lower() == "true":
            raise RuntimeError(
                "SQLite AI worker requires WEB_CONCURRENCY=1; use a shared claimed queue before scaling replicas"
            )
        with SessionLocal() as db:
            backfill_legacy_memory(db)
        if os.getenv("AI_WORKER_ENABLED", "true").lower() == "true":
            start_silent_worker(SessionLocal)
    try:
        yield
    finally:
        await stop_silent_worker()


app = FastAPI(
    title="WordMaster API",
    description="背单词系统后端API",
    lifespan=lifespan,
)


@app.exception_handler(RevisionConflict)
async def revision_conflict_handler(_request: Request, exc: RevisionConflict):
    return JSONResponse(
        status_code=409,
        content={
            "code": "stale_revision",
            "detail": "另一位管理员已更新",
            "current": exc.current,
        },
    )


@app.exception_handler(MaintenanceLocked)
async def maintenance_locked_handler(_request: Request, exc: MaintenanceLocked):
    return JSONResponse(
        status_code=423,
        content={"code": "maintenance_locked", "detail": exc.reason},
    )


@app.middleware("http")
async def request_identity_and_maintenance(request: Request, call_next):
    request.state.request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    is_write = request.method in {"POST", "PUT", "PATCH", "DELETE"}
    login_request = request.url.path == "/api/auth/login"
    if is_write and request.url.path.startswith("/api/") and not login_request:
        session_factory = getattr(request.app.state, "session_factory", SessionLocal)
        with session_factory() as db:
            state = get_system_state(db)
            if state.maintenance_mode:
                return JSONResponse(
                    status_code=423,
                    content={
                        "code": "maintenance_locked",
                        "detail": state.maintenance_reason or "系统正在恢复备份，请稍后再试",
                    },
                    headers={"X-Request-ID": request.state.request_id},
                )
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response

# 根据环境设置允许的域名
if ENV == "production":
    allow_origins = [
        "http://localhost",
        "http://127.0.0.1",
    ]
else:
    allow_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(banks.router)
app.include_router(groups.router)
app.include_router(study.router)
app.include_router(review.router)
app.include_router(backup.router)
app.include_router(audio.router)
app.include_router(settings.router)
app.include_router(ai.router)
app.include_router(ai_evolution.router)
if ENV == "test":
    app.include_router(testing.router)


@app.get("/api/health")
def health_check():
    payload = {"status": "healthy", "test_mode": ENV == "test"}
    if ENV == "test":
        clock = get_clock()
        payload.update({
            "effective_time": clock.now().isoformat(),
            "timezone": clock.timezone_name,
        })
    return payload


# AI 生成图片静态目录
AI_IMAGES_DIR = os.path.join(os.path.dirname(__file__), "..", "ai_images")
os.makedirs(AI_IMAGES_DIR, exist_ok=True)
app.mount("/ai-images", StaticFiles(directory=AI_IMAGES_DIR), name="ai_images")

AI_MEDIA_DIR = media_root()
AI_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/ai-media", StaticFiles(directory=AI_MEDIA_DIR), name="ai_media")

# 前端静态文件（JS/CSS/图片/音频等）
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIR, "assets")), name="assets")
    app.mount("/audio", StaticFiles(directory=os.path.join(FRONTEND_DIR, "audio")), name="audio")

    # SPA fallback: 非 API 路径返回 index.html，由 vue-router 处理前端路由
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = os.path.join(FRONTEND_DIR, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        index = os.path.join(FRONTEND_DIR, "index.html")
        return FileResponse(index) if os.path.isfile(index) else {"detail": "Not Found"}
else:
    @app.get("/")
    def root():
        return {"message": "WordMaster API is running"}
