from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .routers import auth, banks, groups, study, review, backup, audio, settings, ai

app = FastAPI(title="WordMaster API", description="背单词系统后端API")

import os

# 根据环境设置允许的域名
ENV = os.getenv("ENV", "development")
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
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(banks.router)
app.include_router(groups.router)
app.include_router(study.router)
app.include_router(review.router)
app.include_router(backup.router)
app.include_router(audio.router)
app.include_router(settings.router)
app.include_router(ai.router)


@app.get("/api/health")
def health_check():
    return {"status": "healthy"}


# AI 生成图片静态目录
AI_IMAGES_DIR = os.path.join(os.path.dirname(__file__), "..", "ai_images")
os.makedirs(AI_IMAGES_DIR, exist_ok=True)
app.mount("/ai-images", StaticFiles(directory=AI_IMAGES_DIR), name="ai_images")

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
