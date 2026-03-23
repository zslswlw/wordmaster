# WordMaster 部署指南

## 快速开始

### 1. 服务器初始化（只需一次）

```bash
# 进入项目目录
cd /opt/wordmaster

# 初始化 Git 仓库（如果还没有）
git init
git remote add origin <你的Git仓库地址>

# 首次部署
sudo bash deploy/deploy.sh
```

### 2. 日常更新流程

**本地开发：**
```bash
# 1. 修改代码
# 2. 提交并推送
git add .
git commit -m "添加新功能"
git push origin main
```

**服务器更新：**
```bash
# 方法1：完整部署（推荐）
cd /opt/wordmaster
git pull
sudo bash deploy/deploy.sh

# 方法2：仅拉取代码（快速）
cd /opt/wordmaster
git pull
sudo supervisorctl restart wordmaster-backend
```

## 部署脚本功能

`deploy/deploy.sh` 会自动执行以下步骤：

1. **Git 拉取** - 自动拉取最新代码
2. **系统依赖** - 安装 nginx、supervisor、git 等
3. **后端部署** - 创建虚拟环境、安装 Python 依赖
4. **依赖验证** - 检查关键依赖是否安装成功
5. **前端构建** - 安装 npm 依赖、构建生产环境
6. **服务配置** - 配置 Supervisor 和 Nginx
7. **启动服务** - 启动后端、重启 Nginx
8. **音频下载** - 可选：下载单词音频

## 关键特性

### 依赖管理
- **Python 依赖**：`requirements.txt` 中严格锁定版本
- **Node 依赖**：`package-lock.json` 确保一致性
- **自动验证**：部署时验证关键依赖是否安装成功

### Git 集成
- 自动检测 Git 仓库
- 自动拉取最新代码
- 支持分支切换

### 音频管理
- 自动检测音频下载脚本
- 可选批量下载音频
- 支持后台音频同步

## 故障排查

### 依赖问题
```bash
# 重新安装 Python 依赖
cd /opt/wordmaster/backend
source venv/bin/activate
pip install -r requirements.txt --force-reinstall

# 重新安装 Node 依赖
cd /opt/wordmaster/frontend
rm -rf node_modules
npm install
```

### 服务问题
```bash
# 查看后端状态
supervisorctl status wordmaster-backend

# 查看后端日志
tail -f /var/log/wordmaster/backend.out.log
tail -f /var/log/wordmaster/backend.err.log

# 重启服务
sudo supervisorctl restart wordmaster-backend
sudo systemctl restart nginx
```

### Git 问题
```bash
# 强制拉取最新代码
cd /opt/wordmaster
git fetch --all
git reset --hard origin/main

# 查看当前分支
git branch -v
```

## 最佳实践

1. **定期提交**：小步快跑，频繁提交代码
2. **测试后再部署**：本地测试通过后再推送到服务器
3. **备份数据**：定期备份数据库 `wordmaster.db`
4. **监控日志**：部署后查看日志确认无错误

## 文件说明

```
deploy/
├── deploy.sh          # 主部署脚本
└── supervisor-wordmaster.conf  # Supervisor 配置模板

backend/
├── requirements.txt   # Python 依赖
└── scripts/
    └── download_audio.py  # 音频下载脚本

frontend/
├── package.json       # Node 依赖
└── dist/             # 构建输出（自动生成的）
```

## 更新记录

- 2024-03-20: 添加 Git 自动拉取功能
- 2024-03-20: 添加依赖验证步骤
- 2024-03-20: 添加音频自动下载
