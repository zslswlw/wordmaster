#!/bin/bash
# WordMaster 部署脚本
# 用法: sudo bash deploy.sh

set -e  # 遇到错误立即退出

echo "=========================================="
echo "  WordMaster 部署脚本"
echo "=========================================="

# 配置
PROJECT_DIR="/opt/wordmaster"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
LOG_DIR="/var/log/wordmaster"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 1. 安装依赖
echo ""
log_info "步骤 1/7: 安装系统依赖..."
apt-get update
apt-get install -y nginx supervisor python3-venv nodejs npm

# 2. 创建目录
echo ""
log_info "步骤 2/7: 创建项目目录..."
mkdir -p $PROJECT_DIR
mkdir -p $LOG_DIR

# 3. 部署后端
echo ""
log_info "步骤 3/7: 部署后端服务..."
cd $BACKEND_DIR

# 创建虚拟环境
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

# 激活虚拟环境并安装依赖
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

log_info "后端依赖安装完成"

# 4. 部署前端
echo ""
log_info "步骤 4/7: 部署前端..."
cd $FRONTEND_DIR

# 安装依赖
npm install

# 构建生产环境
npm run build

log_info "前端构建完成"

# 5. 配置 Supervisor
echo ""
log_info "步骤 5/7: 配置 Supervisor..."

cat > /etc/supervisor/conf.d/wordmaster.conf << 'EOF'
[program:wordmaster-backend]
directory=/opt/wordmaster/backend
; 使用 gunicorn 生产服务器，绑定本地地址（通过 Nginx 反向代理）
command=/opt/wordmaster/backend/venv/bin/gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000 --access-logfile /var/log/wordmaster/backend.access.log --error-logfile /var/log/wordmaster/backend.error.log
autostart=true
autorestart=true
user=www-data
stderr_logfile=/var/log/wordmaster/backend.err.log
stdout_logfile=/var/log/wordmaster/backend.out.log
; 生产环境变量
environment=PYTHONPATH="/opt/wordmaster/backend",ENV="production"
; 进程管理
stopasgroup=true
killasgroup=true
startsecs=5
startretries=3

; 注意：前端不需要 Supervisor 管理！
; 前端使用 Nginx 直接托管静态文件（dist/ 目录）
; 严禁运行 npm run dev 或 npm run preview
EOF

# 6. 配置 Nginx
echo ""
log_info "步骤 6/7: 配置 Nginx..."

cat > /etc/nginx/sites-available/wordmaster << 'EOF'
server {
    listen 80;
    server_name _;
    
    # 日志配置
    access_log /var/log/nginx/wordmaster.access.log;
    error_log /var/log/nginx/wordmaster.error.log;

    # 前端静态文件
    location / {
        root /opt/wordmaster/frontend/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
        
        # 缓存静态资源
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }

    # 后端 API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # 健康检查
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
EOF

# 启用站点
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/wordmaster /etc/nginx/sites-enabled/wordmaster

# 测试 Nginx 配置
nginx -t

# 7. 启动服务
echo ""
log_info "步骤 7/7: 启动服务..."

# 重载 Supervisor
echo ""
log_info "配置 Supervisor..."
supervisorctl reread
supervisorctl update

# 停止旧的 frontend 进程（如果存在）
log_info "停止可能存在的旧前端进程..."
supervisorctl stop wordmaster-frontend 2>/dev/null || true
supervisorctl remove wordmaster-frontend 2>/dev/null || true

# 启动后端
log_info "启动后端服务..."
supervisorctl start wordmaster-backend || supervisorctl restart wordmaster-backend

# 重启 Nginx
systemctl restart nginx
systemctl enable nginx
systemctl enable supervisor

echo ""
echo "=========================================="
log_info "部署完成!"
echo "=========================================="
echo ""
echo "访问地址: http://你的服务器IP"
echo ""
echo "常用命令:"
echo "  查看后端状态: supervisorctl status wordmaster-backend"
echo "  查看后端日志: tail -f /var/log/wordmaster/backend.out.log"
echo "  重启后端: supervisorctl restart wordmaster-backend"
echo "  重启 Nginx: systemctl restart nginx"
echo ""
echo "=========================================="
