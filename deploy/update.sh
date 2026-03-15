#!/bin/bash
# WordMaster 更新脚本
# 用法: sudo bash update.sh

set -e

PROJECT_DIR="/opt/wordmaster"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

echo "=========================================="
echo "  WordMaster 更新脚本"
echo "=========================================="

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# 1. 更新后端代码
echo ""
log_info "步骤 1/3: 更新后端..."
cd $BACKEND_DIR
source venv/bin/activate

# 安装新依赖
pip install -r requirements.txt

# 2. 更新前端代码
echo ""
log_info "步骤 2/3: 更新前端..."
cd $FRONTEND_DIR

# 安装依赖
npm install

# 重新构建
npm run build

# 3. 重启服务
echo ""
log_info "步骤 3/3: 重启服务..."
supervisorctl restart wordmaster-backend
systemctl restart nginx

echo ""
echo "=========================================="
log_info "更新完成!"
echo "=========================================="
