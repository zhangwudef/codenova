# CodeNova 在线 Demo 部署指南

> 本文档覆盖三种部署方案：**Render Blueprint（推荐）**、**Fly.io**、**手动 Docker**。
> Demo 部署后，访客无需自备 API Key 即可体验仓库解析与问答。

---

## 方案一：Render Blueprint（推荐，零成本）

### 资源需求
| 资源 | 用途 | 免费额度 |
| --- | --- | --- |
| Render 账号 | Web Service + Static Site | 750h/月 |
| Qdrant Cloud 账号 | 向量库 | 1GB / 1 cluster |
| OpenAI API Key | 问答 LLM | 按用量付费（Demo 用 gpt-4o-mini 月成本 <$5） |

### 部署步骤

1. **Fork 仓库**：在 GitHub 上 Fork [zhangwudef/codenova](https://github.com/zhangwudef/codenova) 到自己账号。

2. **申请 Qdrant Cloud**
   - 访问 https://cloud.qdrant.io 注册
   - 创建 Free Cluster（1GB）
   - 记录 `Cluster URL`（形如 `https://xxx.gcp.cloud.qdrant.io:6333`）与 `API Key`

3. **在 Render 创建 Blueprint**
   - 访问 https://dashboard.render.com → New → Blueprint
   - 选择 Fork 的仓库，Render 自动读取 `render.yaml`
   - 填写以下 `sync: false` 环境变量：

   | 变量 | 值 |
   | --- | --- |
   | `QDRANT_URL` | Qdrant Cloud Cluster URL |
   | `QDRANT_API_KEY` | Qdrant Cloud API Key |
   | `OPENAI_API_KEY` | 你的 OpenAI Key |
   | `CODENOVA_API_KEY` | 自定义一串随机字符串（保护 Demo 接口） |
   | `GITHUB_TOKEN`（可选） | GitHub PAT，提升克隆限流 |

4. **更新对外域名**
   - Render 部署完成后会分配 `codenova-backend.onrender.com` 等域名
   - 回到仓库，将 `render.yaml` 中所有 `codenova-backend.onrender.com` 与 `codenova-frontend.onrender.com` 替换为实际域名
   - 同时更新 `CORS_ALLOWED_ORIGINS` 与 `BACKEND_EXTERNAL_HOST`

5. **触发部署**：推送任意 commit 或在 Render Dashboard 点击 Manual Deploy

6. **预索引 Demo 仓库**（让访客立即体验）
   ```bash
   curl -X POST https://codenova-backend.onrender.com/api/v1/repos/parse \
     -H "Content-Type: application/json" \
     -H "X-API-Key: <你的 CODENOVA_API_KEY>" \
     -d '{"repo_url": "https://github.com/pallets/flask.git", "max_files": 100}'
   ```

### 部署验证清单
- [ ] 访问 `https://<frontend>.onrender.com` 能看到前端界面
- [ ] 输入 flask 仓库 URL 能完成解析（约 30-60s）
- [ ] 问答能正常返回答案（首次冷启动可能 30s+）
- [ ] 健康检查 `https://<backend>.onrender.com/health` 返回 `{"status": "ok"}`
- [ ] Swagger 文档 `https://<backend>.onrender.com/docs` 可访问

---

## 方案二：Fly.io（适合需要全球边缘节点）

### 资源需求
- Fly.io 账号（免费额度 3 个 shared-cpu-1x VM）
- Qdrant Cloud（同上）
- OpenAI API Key

### 部署步骤
1. 安装 `flyctl`：`curl -L https://fly.io/install.sh | sh`
2. 登录：`flyctl auth login`
3. 在项目根目录执行：
   ```bash
   flyctl launch --no-deploy --name codenova-backend --dockerfile backend/Dockerfile.prod
   ```
4. 编辑生成的 `fly.toml`，配置环境变量与 volume
5. 部署：`flyctl deploy`
6. 前端可单独部署到 Cloudflare Pages 或 Vercel

---

## 方案三：本地 Docker 体验（无需云账号）

```bash
git clone https://github.com/zhangwudef/codenova.git
cd codenova
cp .env.example .env
# 编辑 .env，至少填入 OPENAI_API_KEY
docker compose -f docker-compose.demo.yml up -d
```
访问 http://localhost:5173

---

## Demo 运维

### 资源监控
- Render Dashboard 可查看 CPU / 内存 / 响应时间
- 设置告警：内存 > 80% 持续 5min 时通知
- Qdrant Cloud 控制台查看 collection 大小

### 成本控制
- Demo 模式已限制 `DEMO_MAX_FILES=150`，避免大仓库 OOM
- LLM 使用 `gpt-4o-mini`，单次问答成本约 $0.001
- 预计月成本：免费 tier + OpenAI ~$5（轻度使用）

### 故障恢复
- Render 自动重启：web service 支持 `autoDeploy` 与 health check
- Qdrant 数据持久化在 Qdrant Cloud，Render 服务重启不丢索引
- 后端 bootstrap 失败时检查 `OPENAI_API_KEY` 与 `QDRANT_URL`

### 更新 Demo
- 修复 bug 后推送到 main 分支，Render 自动重新部署
- 重大变更可先在 PR 预览环境验证

---

## 后续优化方向
1. 接入 Cloudflare CDN 加速前端静态资源
2. 启用 Render 的 PR Preview 环境，每个 PR 自动预览
3. 配置 Sentry 收集线上错误
4. 启用 Celery worker 支持异步解析（需 Redis Cloud 免费 30MB）
5. 接入 Plausible / Umami 隐私友好的访问统计
