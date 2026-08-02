# CodeNova 智码星

> 让每一行代码自己开口说话 —— 基于 AST + 双索引 RAG 的代码理解与文档自动化平台

输入一个代码仓库，输出可问答、可导航、可视化的技术知识库。面向接手老项目的开发者、开源项目维护者、技术团队新人，降低代码理解与文档维护成本。

## 核心能力

| 能力 | 说明 |
|------|------|
| AST 语义切分 | 基于 Tree-sitter，按函数/类/方法粒度切分代码，支持 Python / JS / TS / Java / Go / Rust |
| 双索引检索 | 语义向量索引 + 调用图索引（1-hop 扩展），兼顾语义相似与结构关联 |
| 增量索引 | 基于 Git diff，仅对变更文件重建索引 |
| 可视化 | ReactFlow 依赖图 + Mermaid 调用时序图 |
| RAG 问答 | 带源码定位的自然语言问答，支持流式输出 |
| 文档生成 | 结合 RAG 生成 README / API 文档 / 模块说明 |

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/zhangwudef/codenova.git
cd codenova

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，至少填入 OPENAI_API_KEY

# 3. 启动 Demo 版（3 个服务，约 4GB 内存）
docker compose -f docker-compose.demo.yml up -d

# 4. 访问
# 前端: http://localhost:5173
# 后端 API: http://localhost:8000/docs
```

## 文档导航

- [部署指南](DEPLOYMENT.md) — Render / Fly.io / 本地 Docker
- [性能基准](benchmark.md) — S1 真实基准数据
- [API 参考](api.md) — 完整 RESTful API 文档
- [故障排查](troubleshooting.md) — 常见问题 FAQ
- [架构决策](decisions/0001-record-architecture-decisions.md) — ADR 记录

## 链接

- [GitHub 仓库](https://github.com/zhangwudef/codenova)
- [贡献指南](../CONTRIBUTING.md)
- [更新日志](../CHANGELOG.md)
- [安全政策](../SECURITY.md)
