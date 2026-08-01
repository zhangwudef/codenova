"""依赖图与时序图 API 接口。

对应文档 3.2 / 3.3 节：
- GET /repos/graph?type=dependency&repo_url=...  返回依赖图节点+边
- GET /repos/graph?type=sequence&repo_url=...&entry=...  返回时序图数据

说明：文档原写法 `GET /repos/{repo_url}/graph` 中 repo_url 含斜杠与协议头，
作为路径参数需 {repo_url:path} 且编码复杂。此处调整为 query 参数，
功能等价、更易用，接口路径仍保留 /repos/graph。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from pydantic import BaseModel, Field

from app.services.analyzer.call_graph import call_graph_extractor
from app.services.analyzer.schemas import GraphData, SequenceData
from app.services.github_service import github_service
from app.services.parser.pipeline import ParsingPipeline

router = APIRouter()


class GraphRequest(BaseModel):
    """图查询请求（用于 POST 备用，主接口为 GET）。"""

    repo_url: str = Field(..., description="GitHub 仓库地址")
    branch: str | None = None
    max_files: int = Field(default=200, ge=1, le=2000)
    graph_type: str = Field(default="dependency", description="dependency / sequence")
    entry_function: str | None = Field(default=None, description="时序图入口函数")


def _parse_repo(repo_url: str, branch: str | None, max_files: int):
    """克隆并解析仓库，返回 ParsingResultSummary 与本地路径。

    复用 /repos/parse 的同步流程；阶段四将迁移至 Celery 异步任务。
    """
    logger.info(f"图查询: 克隆 {repo_url}")
    try:
        local_path = github_service.clone(repo_url, branch=branch)
    except Exception as e:
        logger.exception("仓库克隆失败")
        raise HTTPException(status_code=422, detail=f"克隆失败: {e}") from e

    try:
        pipeline = ParsingPipeline()
        summary = pipeline.run(local_path, repo_url=repo_url, max_files=max_files)
        return summary, local_path
    except Exception as e:
        logger.exception("解析管线执行失败")
        raise HTTPException(status_code=500, detail=f"解析失败: {e}") from e
    finally:
        github_service.cleanup(local_path)


@router.get("/graph", response_model=GraphData)
async def get_dependency_graph(
    repo_url: str = Query(..., description="GitHub 仓库地址"),
    branch: str | None = Query(default=None, description="分支名"),
    max_files: int = Query(default=200, ge=1, le=2000),
    node_type: str | None = Query(
        default=None, description="可选：仅保留指定类型节点 module/class/function/interface"
    ),
) -> GraphData:
    """获取仓库依赖图（文档 3.2 节）。

    返回节点（module/class/function/interface）与边（import/call/inherit/implement），
    支持按节点类型过滤。
    """
    summary, _ = _parse_repo(repo_url, branch, max_files)

    try:
        graph = call_graph_extractor.extract(summary.files, repo_url=repo_url)
    except Exception as e:
        logger.exception("依赖图构建失败")
        raise HTTPException(status_code=500, detail=f"图构建失败: {e}") from e

    # 可选：按节点类型过滤
    if node_type:
        allowed = {node_type}
        graph.nodes = [n for n in graph.nodes if n.type.value in allowed]
        keep_ids = {n.id for n in graph.nodes}
        graph.edges = [e for e in graph.edges if e.source in keep_ids and e.target in keep_ids]

    logger.info(f"依赖图: 节点={len(graph.nodes)} 边={len(graph.edges)}")
    return graph


@router.get("/sequence", response_model=SequenceData)
async def get_sequence_diagram(
    repo_url: str = Query(..., description="GitHub 仓库地址"),
    entry: str = Query(..., description="入口函数名（symbol_name 或 qualified_name）"),
    branch: str | None = Query(default=None, description="分支名"),
    max_files: int = Query(default=200, ge=1, le=2000),
    max_depth: int = Query(default=5, ge=1, le=10, description="最大调用深度"),
) -> SequenceData:
    """获取时序图数据（文档 3.3 节）。

    从指定入口函数出发，沿调用关系遍历，生成 Mermaid sequenceDiagram。
    """
    summary, _ = _parse_repo(repo_url, branch, max_files)

    try:
        seq = call_graph_extractor.extract_call_chain(
            summary.files, entry_function=entry, repo_url=repo_url, max_depth=max_depth
        )
    except Exception as e:
        logger.exception("调用链提取失败")
        raise HTTPException(status_code=500, detail=f"时序图生成失败: {e}") from e

    return seq


@router.post("/graph", response_model=GraphData)
async def post_dependency_graph(req: GraphRequest) -> GraphData:
    """POST 形式的依赖图查询（便于携带复杂参数）。

    时序图请使用 GET /repos/sequence。
    """
    summary, _ = _parse_repo(req.repo_url, req.branch, req.max_files)
    graph = call_graph_extractor.extract(summary.files, repo_url=req.repo_url)
    return graph
