# 阿里云轻量服务器 Docker 部署说明（端口 2027）

## 1. 目标
- 部署地址：`112.124.32.196`
- 对外访问端口：`2027`
- 部署方式：Docker Compose
- 数据库：复用你服务器上已存在 MySQL（不新建 DB 容器）

## 2. 已提供文件
- 根目录编排文件：`docker-compose.aliyun-2027.yml`
- 部署环境变量模板：`.env.deploy.example`
- 部署环境变量实档：`.env.deploy`
- 后端镜像定义：`backend/apps/api-gateway/Dockerfile`
- 前端镜像定义：`frontend/Dockerfile`
- 前端反向代理：`frontend/nginx.cbec.conf`

## 3. 部署前检查
1. 阿里云轻量服务器防火墙/安全组放行 `2027/TCP`。
2. 确认数据库可从当前服务器访问：
   - 主机：`112.124.32.196`
   - 端口：`13306`
   - 数据库名：`cbec_sim`（可改）
3. 修改 `.env.deploy`：
   - `CBEC_DATABASE_URL` 中的数据库密码
   - `CBEC_JWT_SECRET` 改成高强度随机串

## 4. 部署命令
在项目根目录执行：

```bash
docker compose --env-file .env.deploy -f docker-compose.aliyun-2027.yml up -d --build
```

查看容器状态：

```bash
docker compose --env-file .env.deploy -f docker-compose.aliyun-2027.yml ps
```

查看日志：

```bash
docker compose --env-file .env.deploy -f docker-compose.aliyun-2027.yml logs -f api
docker compose --env-file .env.deploy -f docker-compose.aliyun-2027.yml logs -f web
```

## 5. 验证方式
1. 健康检查：
   - `http://112.124.32.196:2027/api/health`
2. 前端首页：
   - `http://112.124.32.196:2027`
3. 图片上传访问（若有）：
   - `http://112.124.32.196:2027/uploads/...`

## 6. 更新发布
代码更新后重新构建发布：

```bash
docker compose --env-file .env.deploy -f docker-compose.aliyun-2027.yml up -d --build
```

如需停止：

```bash
docker compose --env-file .env.deploy -f docker-compose.aliyun-2027.yml down
```

## 7. 配置项说明
- `CBEC_DATABASE_URL`：后端数据库连接（不带库名或带库名都可，系统会自动补全）
- `CBEC_DB_NAME`：业务库名（默认 `cbec_sim`）
- `CBEC_JWT_SECRET`：登录鉴权密钥
- `CBEC_CORS_ALLOW_ORIGINS`：前端来源白名单
- `CBEC_CORS_ALLOW_ORIGIN_REGEX`：来源正则白名单
- `CBEC_VITE_API_BASE_URL`：前端打包注入的 API 基地址（本方案使用 `/api` 反向代理）

## 8. 常见问题
- 前端能开但接口 502：
  - 先看 `api` 日志，通常是数据库连接串密码错误或端口不可达。
- 打开页面空白：
  - 查看 `web` 容器日志，确认前端是否构建成功。
- 跨域报错：
  - 检查 `.env.deploy` 中 `CBEC_CORS_ALLOW_ORIGINS` 是否与访问地址一致（本方案应为 `http://112.124.32.196:2027`）。
