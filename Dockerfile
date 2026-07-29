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

RUN chmod +x /app/entrypoint.sh

COPY --from=frontend-build /frontend/dist /app/static

RUN mkdir -p /app/data/ai-media /app/ai_images
ENV DATABASE_URL=sqlite:////app/data/wordmaster.db
ENV AI_MEDIA_DIR=/app/data/ai-media

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD curl -f http://localhost:8000/api/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
