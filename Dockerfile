# Stage 1: 前端构建
FROM node:20-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: 后端
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .

# 启动脚本（自动运行数据库迁移）
RUN chmod +x /app/entrypoint.sh

# 前端构建产物
COPY --from=frontend-build /frontend/dist /app/static

# 数据 & 图片持久化目录
RUN mkdir -p /app/data /app/ai_images
ENV DATABASE_URL=sqlite:////app/data/wordmaster.db

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD curl -f http://localhost:8000/api/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
