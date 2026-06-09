# WordMaster 部署指南

## 部署（Docker）

服务器只需 Docker + Docker Compose，不需要 nginx、supervisor、gunicorn。

```bash
cd /opt/wordmaster
git pull
docker compose down
docker compose up -d --build
```

访问 `http://服务器IP:8000`。

### 验证

```bash
curl http://localhost:8000/api/health   # → {"status":"healthy"}
docker compose ps                        # → status: Up
docker compose logs --tail=20            # 看日志
```

### 数据持久化

- 数据库：`wordmaster_data` volume → `/app/data/wordmaster.db`
- AI 图片：`wordmaster_images` volume → `/app/ai_images/`

### 端口

容器暴露 8000，`compose.yaml` 已做映射。不需要额外配置反向代理。

## 本地开发（非 Docker）

```bash
# 终端 1：后端
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8006 --reload

# 终端 2：前端
cd frontend
npm run dev
# Vite dev server → http://127.0.0.1:5178
# 自动代理 /api 到 localhost:8006
```
