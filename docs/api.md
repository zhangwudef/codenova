# CodeNova API 参考

> Base URL: `http://localhost:8000/api/v1`
> 交互式文档：`http://localhost:8000/docs`（Swagger UI）
> 生产环境替换为实际域名。

所有受保护的接口需要通过 API Key 鉴权（在请求头中携带 `X-API-Key`）。
`/health` 与 `/health/detail` 豁免鉴权。详见 [SECURITY.md](../SECURITY.md)。

---

## 目录

- [系统](#系统)
- [仓库解析](#仓库解析)
- [依赖图与时序图](#依赖图与时序图)
- [RAG 问答](#rag-问答)
- [WebSocket](#websocket)

---

## 系统

### GET /health

轻量健康探针，不依赖外部服务。

**响应 200**
```json
{
  "status": "ok",
  "service": "codenova-backend",
  "version": "0.1.0"
}
```

---

## 仓库解析

### POST /repos/parse

同步克隆并解析 GitHub 仓库，返回解析摘要。不构建向量索引。

**请求体**
| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `repo_url` | string (URL) | 是 | — | GitHub 仓库地址 |
| `branch` | string | 否 | 默认分支 | 分支名 |
| `max_files` | int | 否 | 200 | 最多解析文件数（1–2000） |

**示例**
```bash
curl -X POST http://localhost:8000/api/v1/repos/parse \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your-key>" \
  -d '{"repo_url": "https://github.com/pallets/flask.git", "max_files": 200}'
```

**响应 200** — `ParsingResultSummary`
```json
{
  "repo_url": "https://github.com/pallets/flask.git",
  "total_files": 187,
  "total_symbols": 1245,
  "languages": {"python": 180, "javascript": 5, "other": 2},
  "files": [{"path": "src/flask/app.py", "name": "app.py", "language": "python"}]
}
```

**错误码**
| 状态码 | 说明 |
|--------|------|
| 422 | 仓库克隆失败（URL 无效、私有仓库、网络问题） |
| 500 | 解析管线执行失败 |

---

### POST /repos/parse-async

异步解析（需要 Celery + Redis），返回任务 ID 用于 WebSocket 订阅进度。

**响应 200** — `AsyncParseResponse`
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "repo_url": "https://github.com/pallets/flask.git",
  "status": "queued",
  "ws_url": "ws://localhost:8000/ws/parse/a1b2c3d4"
}
```

---

## 依赖图与时序图

### GET /repos/graph

获取仓库的依赖关系图或调用时序图。

**查询参数**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `repo_url` | string | 是 | 仓库地址 |
| `type` | string | 是 | `dependency`（依赖图）或 `sequence`（时序图） |
| `entry` | string | 否 | 时序图入口函数名（type=sequence 时使用） |

**示例**
```bash
# 依赖图
curl "http://localhost:8000/api/v1/repos/graph?type=dependency&repo_url=https://github.com/pallets/flask.git" \
  -H "X-API-Key: <your-key>"

# 调用时序图
curl "http://localhost:8000/api/v1/repos/graph?type=sequence&repo_url=https://github.com/pallets/flask.git&entry=run" \
  -H "X-API-Key: <your-key>"
```

---

## RAG 问答

### POST /rag/index

为指定仓库构建向量索引（AST 切分 → Embedding → Qdrant 入库 + 调用图索引）。

**请求体**
| 字段 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `repo_url` | string | 是 | — | 仓库地址 |
| `branch` | string | 否 | 默认分支 | 分支名 |
| `max_files` | int | 否 | 200 | 最多索引文件数 |
| `chunk_strategy` | string | 否 | `ast` | 切分策略：`ast` / `semantic` / `fixed` |

**响应 200** — `IndexResult`
```json
{
  "repo_url": "https://github.com/pallets/flask.git",
  "total_files": 187,
  "total_chunks": 452,
  "total_embeddings": 452,
  "collection_name": "codenova_code_chunks",
  "elapsed_seconds": 38.2
}
```

---

### POST /rag/ask

基于已构建的索引回答自然语言问题，返回带源码定位的答案。

**请求体**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `question` | string | 是 | 自然语言问题 |
| `repo_url` | string | 是 | 仓库地址 |

**响应 200** — `QAAnswer`
```json
{
  "question": "请求上下文是在哪里创建的？",
  "answer": "请求上下文 RequestContext 在 src/flask/ctx.py 的 RequestContext 类中创建...",
  "sources": [
    {
      "file_path": "src/flask/ctx.py",
      "line_start": 42,
      "line_end": 85,
      "symbol": "RequestContext.__init__",
      "score": 0.89
    }
  ]
}
```

---

### POST /rag/ask-stream

与 `/rag/ask` 相同，但以 Server-Sent Events 流式返回答案（打字机效果）。

**响应**：`text/event-stream`

---

### POST /rag/index-incremental

基于 Git diff 对变更文件做增量索引（需提供上次索引的 commit hash）。

**请求体**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `repo_url` | string | 是 | 仓库地址 |
| `since_commit` | string | 是 | 上次索引的 commit hash |

---

### POST /rag/generate-doc

结合 RAG 检索生成文档（README / API 文档 / 模块说明）。

**请求体** — `DocGenerateRequest`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `repo_url` | string | 是 | 仓库地址 |
| `doc_type` | string | 是 | `readme` / `api` / `module` |
| `target_path` | string | 否 | 指定模块路径（doc_type=module 时） |

---

### POST /rag/persist-qa

将高质量问答固化为 Markdown 持久化存储（需 MinIO）。

**请求体** — `QAPersistRequest`
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `question` | string | 是 | 原始问题 |
| `answer` | string | 是 | 答案内容 |
| `repo_url` | string | 是 | 仓库地址 |
| `sources` | array | 否 | 源码引用列表 |

---

## WebSocket

### WS /ws/parse/{task_id}

订阅异步解析任务的实时进度推送。

**消息格式**
```json
{
  "step_id": "cloning",
  "step": "正在克隆仓库...",
  "progress": 15,
  "error": null
}
```

**步骤枚举**：`cloning` → `parsing` → `chunking` → `embedding` → `indexing` → `done`

---

## 错误处理

所有错误响应遵循统一格式：

```json
{
  "detail": "错误描述信息"
}
```

| 状态码 | 说明 |
|--------|------|
| 400 | 请求参数错误 |
| 401 | API Key 缺失或无效 |
| 404 | 资源不存在 |
| 422 | 请求体验证失败 / 仓库克隆失败 |
| 500 | 服务器内部错误 |
| 503 | 外部依赖服务不可用（Qdrant / OpenAI） |
