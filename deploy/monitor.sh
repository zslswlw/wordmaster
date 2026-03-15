#!/bin/bash
# WordMaster 监控脚本
# 用法: bash monitor.sh

echo "=========================================="
echo "  WordMaster 服务状态"
echo "=========================================="
echo ""

# 检查后端服务
echo "【后端服务状态】"
supervisorctl status wordmaster-backend 2>/dev/null || echo "后端服务未运行"
echo ""

# 检查 Nginx
echo "【Nginx 状态】"
systemctl is-active nginx &>/dev/null && echo "Nginx: 运行中 ✓" || echo "Nginx: 未运行 ✗"
echo ""

# 检查端口
echo "【端口监听】"
echo "端口 80 (Nginx):"
ss -tlnp | grep :80 || echo "  未监听"
echo ""
echo "端口 8000 (后端):"
ss -tlnp | grep :8000 || echo "  未监听"
echo ""

# 检查 API 健康
echo "【API 健康检查】"
if curl -s http://localhost:8000/api/health > /dev/null; then
    echo "后端 API: 正常 ✓"
else
    echo "后端 API: 异常 ✗"
fi
echo ""

# 显示最近日志
echo "【最近后端日志 (最后5行)】"
tail -n 5 /var/log/wordmaster/backend.out.log 2>/dev/null || echo "暂无日志"
echo ""

# 显示系统资源
echo "【系统资源】"
echo "CPU 使用率: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)%"
echo "内存使用:"
free -h | grep "Mem:"
echo "磁盘使用:"
df -h / | tail -1
echo ""

echo "=========================================="
echo "监控完成"
echo "=========================================="
