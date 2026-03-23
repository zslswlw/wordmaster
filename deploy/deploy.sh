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

# 0. Git 拉取最新代码
echo ""
log_info "步骤 0/8: 拉取最新代码..."
cd $PROJECT_DIR

# 检查是否是 git 仓库
if [ -d ".git" ]; then
    log_info "检测到 Git 仓库，拉取最新代码..."
    git pull
    log_info "代码更新完成"
else
    log_warn "未检测到 Git 仓库，跳过代码更新"
    log_warn "建议初始化 Git 仓库: git init && git remote add origin <your-repo>"
fi

# 1. 安装依赖
echo ""
log_info "步骤 1/8: 安装系统依赖..."
apt-get update
apt-get install -y nginx supervisor python3-venv nodejs npm git

# 2. 创建目录
echo ""
log_info "步骤 2/8: 创建项目目录..."
mkdir -p $PROJECT_DIR
mkdir -p $LOG_DIR

# 3. 部署后端
echo ""
log_info "步骤 3/8: 部署后端服务..."
cd $BACKEND_DIR

# 创建虚拟环境
if [ ! -d "venv" ]; then
    python3 -m venv venv
    log_info "创建虚拟环境"
fi

# 激活虚拟环境并安装依赖
source venv/bin/activate

# 检查 requirements.txt 是否有更新
if [ -f "requirements.txt" ]; then
    log_info "安装/更新 Python 依赖..."
    pip install --upgrade pip
    pip install -r requirements.txt
    log_info "后端依赖安装完成"
else
    log_warn "未找到 requirements.txt"
fi

# 验证关键依赖
log_info "验证依赖..."
python -c "import fastapi, sqlalchemy, requests" || {
    log_error "依赖验证失败！"
    exit 1
}
log_info "依赖验证通过"

# 4. 部署前端
echo ""
log_info "步骤 4/8: 部署前端..."
cd $FRONTEND_DIR

# 检查 package.json 是否有更新
if [ -f "package.json" ]; then
    log_info "安装前端依赖..."
    npm install
    
    log_info "构建生产环境..."
    npm run build
    log_info "前端构建完成"
else
    log_warn "未找到 package.json"
fi

# 5. 配置 Supervisor
echo ""
log_info "步骤 5/8: 配置 Supervisor..."

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
log_info "步骤 6/8: 配置 Nginx..."

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
    
    # 音频文件特殊处理（支持 Service Worker 缓存）
    location /audio/ {
        root /opt/wordmaster/frontend/public;
        expires 1y;
        add_header Cache-Control "public, immutable";
        add_header Service-Worker-Allowed "/";
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
    
    # Service Worker 文件（不缓存）
    location /service-worker.js {
        root /opt/wordmaster/frontend/dist;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma "no-cache";
        expires 0;
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
log_info "步骤 7/8: 启动服务..."

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

# 8. 可选：下载音频
echo ""
log_info "步骤 8/8: 检查音频文件..."
if [ -f "$BACKEND_DIR/scripts/download_audio.py" ]; then
    log_info "发现音频下载脚本"
    read -p "是否下载音频文件？(y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cd $BACKEND_DIR
        python scripts/download_audio.py --sync --workers 5 || {
            log_warn "音频下载失败，但部署继续"
        }
    else
        log_info "跳过音频下载，稍后可在音频管理页面操作"
    fi
else
    log_info "音频下载脚本不存在，跳过"
fi

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
echo "  手动拉取代码: cd /opt/wordmaster && git pull"
echo "  手动部署: sudo bash /opt/wordmaster/deploy/deploy.sh"
echo ""
echo "Git 工作流:"
echo "  1. 本地开发: git add . && git commit -m 'xxx' && git push"
echo "  2. 服务器部署: cd /opt/wordmaster && git pull && sudo bash deploy/deploy.sh"
echo ""
echo "=========================================="