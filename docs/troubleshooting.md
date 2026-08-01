# 故障排查与常见问题（FAQ）

---

## 安装与启动

### Q: `docker compose up -d` 后后端容器不断重启

**可能原因**：`.env` 文件缺失或 `OPENAI_API_KEY` 未填写。

**解决**：
```bash
cp .env.example .env
# 编辑 .env，至少填入 OPENAI_API_KEY
docker compose -f docker-compose.demo.yml up -d
```

查看日志定位具体错误：
```bash
docker logs codenova-demo-backend --tail 50
```

---

### Q: 后端启动报错 `ModuleNotFoundError: No module named 'app'`

**原因**：未在 `backend/` 目录下运行，或未安装依赖。

**解决**：
```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

---

### Q: 前端 `npm install` 失败或极慢

**解决**：使用国内镜像
```bash
npm install --registry=https://registry.npmmirror.com
```

---

### Q: Docker 构建时 pip install 超时

**原因**：默认使用官方 PyPI 源，国内网络可能超时。

**解决**：使用 `PIP_INDEX_URL` build-arg 指定镜像
```bash
docker compose build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
```

---

## 模型与依赖

### Q: 首次启动卡在下载 `bge-m3` Embedding 模型

**原因**：`BAAI/bge-m3` 模型约 2GB，首次需从 HuggingFace 下载。

**解决**：
1. 耐心等待（视网络 5–20 分钟）
2. 国内用户设置 HF 镜像：
   ```bash
   export HF_ENDPOINT=https://hf-mirror.com
   ```
3. 或预下载模型到本地，在 `.env` 中指定路径

---

### Q: 问答返回 503 或 `OpenAI API error`

**可能原因**：
- `OPENAI_API_KEY` 无效或余额不足
- `OPENAI_BASE_URL` 指向的服务不可达
- 使用 Qwen 等兼容服务时 URL 格式错误

**排查**：
```bash
# 验证 API Key 是否有效
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

---

### Q: Qdrant 连接失败 `Connection refused`

**原因**：Qdrant 容器未启动或健康检查未通过。

**解决**：
```bash
# 检查 Qdrant 容器状态
docker ps | grep qdrant
# 查看健康状态
curl http://localhost:6333/healthz
# 重启 Qdrant
docker restart codenova-demo-qdrant
```

---

## 解析与索引

### Q: 解析大仓库时后端 OOM 崩溃

**原因**：Demo 模式未限制文件数，大仓库内存占用过高。

**解决**：
1. 设置 `DEMO_MAX_FILES=150`（或更低）
2. 使用 `max_files` 参数限制解析文件数：
   ```bash
   curl -X POST http://localhost:8000/api/v1/repos/parse \
     -d '{"repo_url": "...", "max_files": 100}'
   ```
3. 增大容器内存限制（完整版 docker-compose.yml）

---

### Q: GitHub 匿名克隆被限流（HTTP 429）

**原因**：未配置 `GITHUB_TOKEN`，匿名克隆每小时限 60 次。

**解决**：
1. 创建 GitHub Personal Access Token（需 `public_repo` 权限）
2. 在 `.env` 中设置 `GITHUB_TOKEN=ghp_xxxx`

---

### Q: AST 切分对某些文件回退到固定长度

**原因**：Tree-sitter 不支持该语言，或文件语法有错误导致解析失败。

**说明**：这是预期行为——`ASTChunkStrategy` 内置三级回退策略（AST → 语义 → 固定长度），确保不丢内容。支持的语言：Python / JavaScript / TypeScript / Java / Go / Rust。

---

### Q: 增量索引报错 `commit hash not found`

**原因**：`since_commit` 指定的 commit 在当前仓库不存在（可能被 rebase 删除）。

**解决**：使用全量索引重建：
```bash
curl -X POST http://localhost:8000/api/v1/rag/index \
  -d '{"repo_url": "..."}'
```

---

## 前端

### Q: 页面显示「屏幕宽度不足」

**原因**：CodeNova 三栏布局需至少 1024px 宽度。

**解决**：扩大浏览器窗口，或在桌面端访问。

---

### Q: 依赖图或时序图不显示

**可能原因**：
- 仓库尚未解析（先调用 `/repos/parse`）
- ReactFlow / Mermaid 组件加载失败（检查浏览器控制台）
- 解析结果中无调用关系（仓库太小或全是配置文件）

---

### Q: WebSocket 连接立即断开

**原因**：使用异步解析但未启动 Celery Worker（完整版才包含）。

**解决**：使用同步解析（`POST /repos/parse`），或启动完整版：
```bash
docker compose up -d  # 完整版含 celery-worker
```

---

## 部署

### Q: Render 部署后健康检查失败

**排查步骤**：
1. 查看 Render Dashboard → Logs
2. 确认 `OPENAI_API_KEY`、`QDRANT_URL`、`QDRANT_API_KEY` 已配置
3. 验证 `/health` 返回 200：
   ```bash
   curl https://<your-backend>.onrender.com/health
   ```
4. 首次部署冷启动可能需 30s+，Render 免费版有休眠机制

---

### Q: CORS 报错 `blocked by CORS policy`

**原因**：`CORS_ALLOWED_ORIGINS` 未包含前端域名。

**解决**：在 `.env` 或 Render 环境变量中设置：
```bash
CORS_ALLOWED_ORIGINS=https://your-frontend.onrender.com
```

---

## 仍无法解决？

1. 查看完整日志：`docker logs codenova-demo-backend -f`
2. 搜索 [现有 Issues](https://github.com/zhangwudef/codenova/issues)
3. 提交 Bug Report（使用 Issue 模板，附上日志与环境信息）
4. 安全问题请按 [SECURITY.md](../SECURITY.md) 私密报告
