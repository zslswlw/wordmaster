from fastapi import FastAPI
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

# AI 生成图片静态目录
AI_IMAGES_DIR = os.path.join(os.path.dirname(__file__), "..", "ai_images")
os.makedirs(AI_IMAGES_DIR, exist_ok=True)
app.mount("/ai-images", StaticFiles(directory=AI_IMAGES_DIR), name="ai_images")

# 生产环境: 托管前端静态文件
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
else:
    @app.get("/")
    def root():
        return {"message": "WordMaster API is running"}


@app.get("/api/health")
def health_check():
    return {"status": "healthy"}
