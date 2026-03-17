#!/bin/bash
# 部署脚本

echo "=== 开始部署 ==="

# 拉取最新代码
echo "拉取代码..."
git pull

# 安装前端依赖
echo "安装前端依赖..."
cd frontend
npm install

# 构建前端
echo "构建前端..."
npm run build

# 重启服务（根据你的实际情况修改）
echo "重启服务..."
# systemctl restart your-service

echo "=== 部署完成 ==="
