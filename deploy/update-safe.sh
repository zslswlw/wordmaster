#!/bin/bash
# WordMaster 安全更新脚本
# 用于更新已部署的服务，修复安全问题

set -e

echo "=========================================="
echo "  WordMaster 安全更新脚本"
echo "=========================================="

PROJECT_DIR="/opt/wordmaster"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 1. 停止危险服务
echo ""
log_info "步骤 1/6: 停止危险服务..."

# 停止 Vite 开发服务器
log_warn "停止所有 Node 进程（Vite 开发服务器）..."
killall -9 node 2>/dev/null || true
killall -9 vite 2>/dev/null || true

# 停止旧的 Supervisor 前端进程
log_warn "停止 Supervisor 前端进程..."
supervisorctl stop wordmaster-frontend 2>/dev/null || true
supervisorctl remove wordmaster-frontend 2>/dev/null || true

# 2. 拉取代码
echo ""
log_info "步骤 2/6: 拉取最新代码..."
cd $PROJECT_DIR
git pull

# 3. 更新后端
echo ""
log_info "步骤 3/6: 更新后端..."
cd $BACKEND_DIR
source venv/bin/activate
pip install -r requirements.txt

# 安装 gunicorn（如果没有）
pip install gunicorn

log_info "后端更新完成"

# 4. 更新前端
echo ""
log_info "步骤 4/6: 更新前端..."
cd $FRONTEND_DIR
npm install
npm run build

log_info "前端构建完成"

# 5. 更新 Supervisor 配置
echo ""
log_info "步骤 5/6: 更新 Supervisor 配置..."

cat > /etc/supervisor/conf.d/wordmaster.conf << 'EOF'
[program:wordmaster-backend]
directory=/opt/wordmaster/backend
command=/opt/wordmaster/backend/venv/bin/gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000 --access-logfile /var/log/wordmaster/backend.access.log --error-logfile /var/log/wordmaster/backend.error.log
autostart=true
autorestart=true
user=www-data
stderr_logfile=/var/log/wordmaster/backend.err.log
stdout_logfile=/var/log/wordmaster/backend.out.log
environment=PYTHONPATH="/opt/wordmaster/backend",ENV="production"
stopasgroup=true
killasgroup=true
startsecs=5
startretries=3
EOF

# 6. 重启服务
echo ""
log_info "步骤 6/6: 重启服务..."

# 重载 Supervisor
supervisorctl reread
supervisorctl update
supervisorctl restart wordmaster-backend

# 重启 Nginx
systemctl restart nginx

echo ""
echo "=========================================="
log_info "安全更新完成!"
echo "=========================================="
echo ""
echo "验证："
echo "  1. 检查端口 5173/5713: netstat -tlnp | grep -E '5173|5713'"
echo "  2. 检查后端状态: supervisorctl status wordmaster-backend"
echo "  3. 访问网站测试功能"
echo ""
