# 背单词系统部署指南

## 环境要求

- Python 3.10+
- Node.js 16+
- Anaconda (推荐)

## 后端部署

### 1. 创建 Conda 环境

```bash
conda create -n beidanci python=3.10
conda activate beidanci
```

### 2. 安装依赖

```bash
cd backend
pip install -r requirements.txt
```

### 3. 启动服务

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 前端部署

### 1. 安装依赖

```bash
cd frontend
npm install
```

### 2. 开发模式

```bash
npm run dev
```

### 3. 生产构建

```bash
npm run build
```

构建产物在 `dist/` 目录。

## 版本锁定说明

- `requirements.txt` - 锁定 Python 包版本
- `package-lock.json` - 锁定 Node.js 包版本
- 部署时请使用这些锁定文件安装依赖

## 常见问题

### bcrypt 版本错误

如果遇到 `AttributeError: module 'bcrypt' has no attribute '__about__'`，请确保安装 `bcrypt==4.0.1`。

### CORS 错误

确保后端 `main.py` 中的 `allow_origins` 包含前端地址。
