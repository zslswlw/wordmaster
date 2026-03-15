from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import auth, banks, groups, study, review, backup

app = FastAPI(title="WordMaster API", description="背单词系统后端API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境建议改为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(banks.router)
app.include_router(groups.router)
app.include_router(study.router)
app.include_router(review.router)
app.include_router(backup.router)


@app.get("/")
def root():
    return {"message": "WordMaster API is running"}


@app.get("/api/health")
def health_check():
    return {"status": "healthy"}
