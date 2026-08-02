# CodeNova 智码星 — Demo 仓库清单

> 用于端到端全链路测试的公开 GitHub 仓库

## 推荐 Demo 仓库

### 1. octocat/Hello-World（极简验证）
- **URL**: https://github.com/octocat/Hello-World
- **规模**: 极小（< 10 文件）
- **用途**: 验证基本解析流程、Git 克隆能力
- **验证要点**:
  - 解析管线能正常运行
  - 生成依赖图（若适用）
  - RAG 问答基本可用

### 2. pallets/flask（中型 Python 项目）
- **URL**: https://github.com/pallets/flask
- **规模**: 中型（~200+ 文件，Python）
- **用途**: 验证多文件解析、AST 切分、调用图
- **验证要点**:
  - 多文件批量解析
  - Python AST 切分准确性
  - 调用关系图生成
  - RAG 问答覆盖多文件

### 3. facebook/react（大型 TS 项目）
- **URL**: https://github.com/facebook/react
- **规模**: 大型（1000+ 文件，TypeScript/JS）
- **用途**: 验证大仓库压力测试、增量更新
- **验证要点**:
  - 大仓库解析性能
  - TypeScript/JavaScript 混合解析
  - 增量文档更新（`POST /rag/index-incremental`）
  - 内存使用和超时处理

### 4. d3/d3（可视化项目）
- **URL**: https://github.com/d3/d3
- **规模**: 中型（~300 文件，JavaScript）
- **用途**: 验证前端项目解析
- **验证要点**:
  - JavaScript 项目解析
  - 依赖关系可视化
  - 前端代码问答

## 端到端验证流程

### 流程 1：仓库解析 → 可视化
```
POST /api/v1/repos/parse
  URL: {repo_url}
  → 获取 task_id
  → WebSocket 订阅进度
  → GET /api/v1/repos/{repo_url}/graph?type=dependency
  → GET /api/v1/repos/{repo_url}/graph?type=sequence&entry={func}
```

### 流程 2：RAG 问答
```
POST /api/v1/rag/index
  URL: {repo_url}
  → POST /api/v1/rag/ask
  query: "这个项目的入口在哪里？"
  → POST /api/v1/rag/ask
  query: "XXX 函数的作用是什么？"
```

### 流程 3：增量更新
```
POST /api/v1/rag/index-incremental
  URL: {repo_url}
  since_commit: {上次索引的 commit}
  → 验证只重新索引变更文件
```

## 注意事项

- 无 GitHub Token 时，匿名克隆受限（每小时 60 次）
- 建议使用 GitHub Token 以提高速率限制
- 大仓库解析可能需要较长时间
- 首次使用需等待 Embedding 模型加载
