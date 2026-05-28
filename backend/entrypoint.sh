#!/bin/bash
set -e

echo "=== WordMaster Docker Entrypoint ==="

# 运行数据库迁移（幂等，安全）
echo "Running database migration..."
python /app/migrate.py

echo "Starting application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
