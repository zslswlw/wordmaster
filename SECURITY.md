# 安全部署指南

## ⚠️ 重要安全警告

### 1. Vite 开发服务器

**绝对不要在生产环境运行 `npm run dev` 或 `vite` 开发服务器！**

- Vite 开发服务器（端口 5173/5713）不是为生产环境设计的
- 它会暴露源代码、环境变量和敏感信息
- 生产环境应该使用 `npm run build` 构建的静态文件

### 2. 生产环境正确部署方式

#### 前端部署

```bash
cd frontend
npm install
npm run build
```

构建产物在 `dist/` 目录，使用 Nginx/Apache 等 Web 服务器托管。

#### Nginx 配置示例

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        root /opt/wordmaster/frontend/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }
    
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

#### 后端部署

```bash
# 设置生产环境变量
export ENV=production

# 启动后端（使用 Gunicorn 或 Uvicorn）
cd backend
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000
```

### 3. 安全加固清单

- [ ] 停止所有 Vite 开发服务器进程
- [ ] 使用 Nginx/Apache 托管前端静态文件
- [ ] 后端绑定到 127.0.0.1（本地）或内网 IP
- [ ] 配置防火墙，只开放 80/443 端口
- [ ] 设置 `ENV=production` 环境变量
- [ ] 修改 CORS 允许域名，不要使用 `*`
- [ ] 启用 HTTPS（Let's Encrypt 免费证书）
- [ ] 定期更新依赖包

### 4. 检查并停止开发服务器

```bash
# 查找 Vite 进程
ps aux | grep vite

# 停止 Vite 进程
killall -9 node
killall -9 vite

# 检查端口占用
netstat -tlnp | grep 5173
netstat -tlnp | grep 5713
```

### 5. 环境变量配置

创建 `.env` 文件：

```bash
# 后端 .env
ENV=production
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///./wordmaster.db
```

## 常见问题

### Q: 如何确认生产环境部署正确？

A: 检查以下几点：
1. 访问网站时，浏览器开发者工具看不到 Vue 源码
2. 网络请求中没有 5173/5713 端口的请求
3. 响应头包含正确的服务器信息（Nginx/Apache）
4. 后端 API 只能通过域名访问，不能直接访问 8000 端口

### Q: 发现 5173 端口还在运行怎么办？

A: 立即执行：
```bash
# 停止所有 Node 进程
killall -9 node

# 检查是否还有进程在监听 5173
lsof -i :5173

# 如果有，记录 PID 并杀死
kill -9 <PID>
```
