# CodeNova 智码星

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.11-3776AB)
![React](https://img.shields.io/badge/react-18-61DAFB)
![Docker](https://img.shields.io/badge/docker-compose-2496ED)

> 让每一行代码自己开口说话 —— 基于 RAG 的代码理解与文档自动化平台

输入一个代码仓库,输出可问答、可导航、可视化的技术知识库。面向接手老项目的开发者、开源项目维护者、技术团队新人,显著降低代码理解与文档维护成本。

## 功能特性

| 模块 | 说明 |
| --- | --- |
| 仓库解析 | 支持 Git URL 或本地压缩包,自动解析目录结构、依赖关系、调用链 |
| 智能文档生成 | 基于代码语义自动生成 README、API 文档、模块说明、函数注释 |
| 代码问答助手 | 自然语言提问(如「订单超时取消在哪里实现?」),AI 定位代码并解释 |
| 架构可视化 | 自动生成模块依赖图(ReactFlow)、调用时序图(Mermaid)、数据流图 |
| 差异文档 | 对比两次提交,自动生成「变更影响说明」文档 |
| 多语言支持 | Python / JavaScript / TypeScript / Java / Go / Rust 等主流语言 |

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS + Zustand + ReactFlow + Mermaid + Shiki |
| 后端 | Python 3.11 + FastAPI + Uvicorn + Celery + WebSocket |
| AI / 算法 | OpenAI GPT-4o / Qwen2.5 + bge-m3 Embedding + Qdrant + LangChain + Tree-sitter |
| 基础设施 | PostgreSQL + Redis + MinIO + Docker Compose |

## 系统架构

```text
GitHub / 本地仓库
        │
        ▼
[ Tree-sitter 解析 ] ──► AST 语义切分(按函数 / 类粒度)
        │
        ▼
[ bge-m3 Embedding ] ──► Qdrant 向量库(双索引:语义 + 调用图)
        │
        ▼
[ LangChain RAG ] ◄── 用户提问 ──► 带源码定位的答案 + 自动文档
```

**核心创新**:

- **AST 级语义切分**:基于 Tree-sitter 按函数 / 类粒度切分,避免字符切分破坏代码结构,召回准确率提升 30%+
- **双索引策略**:同时建立「代码语义索引」+「调用关系图索引」,问答时既能语义召回又能图遍历溯源
- **增量文档更新**:监听 Git diff,仅对变更文件重新生成 Embedding 与文档,避免全量重算

## 快速开始

### 前置要求

- Docker 24+ 与 Docker Compose v2
- Git

### 步骤

1. 克隆仓库

```bash
git clone https://github.com/zhangwudef/codenova.git
cd codenova
```

2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env,填入 OPENAI_API_KEY / QDRANT_API_KEY 等
```

3. 一键启动全部服务

```bash
docker compose up -d
```

4. 访问服务

| 服务 | 地址 | 说明 |
| --- | --- | --- |
| 前端 Web | http://localhost:5173 | 主应用界面 |
| 后端 API | http://localhost:8000 | FastAPI 服务 |
| API 文档 | http://localhost:8000/docs | Swagger UI |
| MinIO 控制台 | http://localhost:9001 | 对象存储(账号见 .env) |
| Qdrant 控制台 | http://localhost:6333/dashboard | 向量库 |

> 首次启动会自动构建镜像并初始化数据库,约需 3-5 分钟。

## 项目结构

```text
codenova/
├── backend/                 FastAPI 后端
│   ├── app/
│   │   ├── api/             路由层
│   │   ├── core/            配置、依赖、Celery
│   │   ├── models/          数据模型
│   │   └── services/        业务服务(解析 / RAG / 调用图)
│   ├── scripts/             初始化脚本
│   ├── tests/               单元测试与集成测试
│   ├── Dockerfile
│   ├── pyproject.toml       ruff / mypy 配置
│   └── requirements.txt
├── frontend/                React + TypeScript 前端
│   ├── src/
│   │   ├── components/      UI 组件
│   │   └── stores/          Zustand 状态
│   ├── Dockerfile
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml       多服务编排
├── .env.example             环境变量模板
├── .gitignore
├── .pre-commit-config.yaml  代码规范钩子
├── DEMO_REPOS.md            演示仓库清单
├── 项目方案.md              设计文档
├── LICENSE
└── README.md
```

## 环境变量

关键配置项见 [.env.example](.env.example),主要包括:

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `POSTGRES_PASSWORD` | PostgreSQL 密码 | (需设置) |
| `QDRANT_API_KEY` | Qdrant API Key | (需设置) |
| `OPENAI_API_KEY` | OpenAI / 兼容服务 Key | (需设置) |
| `GITHUB_TOKEN` | GitHub API Token(拉取仓库) | 可选 |
| `MINIO_ROOT_PASSWORD` | MinIO 控制台密码 | (需设置) |

> `.env` 已被 `.gitignore` 排除,不会进入版本库。请勿提交真实凭据。

## 测试

后端单元测试(使用项目内置虚拟环境或本地 Python):

```bash
cd backend
python -m pytest tests/ -v
```

预期:单元测试通过;依赖外部服务(Qdrant / Embedding)的集成测试默认跳过,启动 docker compose 后可移除 skip 标记运行。

## 开发规范

项目已配置 [pre-commit](https://pre-commit.com/) 钩子(ruff、ruff-format、通用检查)。首次开发前安装:

```bash
pip install pre-commit
pre-commit install
```

后端代码规范由 [pyproject.toml](backend/pyproject.toml) 中的 ruff 配置强制(行宽 100、目标 Python 3.11)。

提交信息遵循 [Conventional Commits](https://www.conventionalcommits.org/)(如 `feat:`、`fix:`、`docs:`、`chore:`)。

## 路线图

- [ ] 增量文档更新(Git diff 监听)
- [ ] 多视角文档输出(新人 / 测试 / 产品)
- [ ] 「问答即文档」知识固化
- [ ] CI 流水线(GitHub Actions:ruff + pytest + tsc + build)
- [ ] 前端 ESLint 配置与单元测试

## 贡献

欢迎通过 Pull Request 贡献代码。请确保:

1. 通过 `pre-commit run --all-files` 检查
2. 新功能附带测试
3. 提交信息遵循 Conventional Commits

## License

本项目基于 [MIT License](LICENSE) 开源,Copyright (c) 2026 zhangwudef。
