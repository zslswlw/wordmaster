from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import auth, banks, groups, study, review, backup, audio

app = FastAPI(title="WordMaster API", description="背单词系统后端API")

import os

# 根据环境设置允许的域名
ENV = os.getenv("ENV", "development")
if ENV == "production":
    allow_origins = [
        "http://localhost",
        "http://127.0.0.1",
        # 添加你的生产域名，例如：
        # "https://your-domain.com",
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


@app.get("/")
def root():
    return {"message": "WordMaster API is running"}


@app.get("/api/health")
def health_check():
    return {"status": "healthy"}
