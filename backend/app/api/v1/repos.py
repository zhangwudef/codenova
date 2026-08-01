"""仓库解析接口。

提供两种解析方式：
- POST /repos/parse        同步解析（阶段一，用于快速预览）
- POST /repos/parse-async  异步解析（阶段三，Celery 任务 + WebSocket 进度推送）
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field, HttpUrl

from app.services.github_service import github_service
from app.services.parser.pipeline import ParsingPipeline
from app.services.parser.schemas import ParsingResultSummary

router = APIRouter()


class ParseRequest(BaseModel):
    repo_url: HttpUrl = Field(..., description="GitHub 仓库地址")
    branch: str | None = Field(default=None, description="分支名，默认为默认分支")
    max_files: int = Field(default=200, ge=1, le=2000, description="最多解析文件数")


class AsyncParseResponse(BaseModel):
    """异步解析任务提交响应。"""

    task_id: str = Field(..., description="Celery 任务 ID，用于订阅 WebSocket 进度")
    repo_url: str
    status: str = Field(default="queued", description="任务状态")
    ws_url: str = Field(..., description="WebSocket 订阅地址")


@router.post("/parse", response_model=ParsingResultSummary)
async def parse_repo(req: ParseRequest) -> ParsingResultSummary:
    """克隆并解析指定 GitHub 仓库，返回解析摘要（同步）。

    用于快速预览，不构建向量索引。完整流程请使用 POST /repos/parse-async。
    """
    url = str(req.repo_url)
    logger.info(f"收到同步解析请求: {url} (branch={req.branch})")
    try:
        local_path = github_service.clone(url, branch=req.branch)
    except Exception as e:
        logger.exception("仓库克隆失败")
        raise HTTPException(status_code=422, detail=f"克隆失败: {e}") from e

    pipeline = ParsingPipeline()
    try:
        summary = pipeline.run(local_path, repo_url=url, max_files=req.max_files)
    except Exception as e:
        logger.exception("解析管线执行失败")
        raise HTTPException(status_code=500, detail=f"解析失败: {e}") from e
    finally:
        github_service.cleanup(local_path)

    logger.info(
        f"解析完成: 文件={summary.total_files} 符号={summary.total_symbols} "
        f"代码块={summary.total_chunks} 耗时={summary.elapsed_seconds:.2f}s"
    )
    return summary


@router.post("/parse-async", response_model=AsyncParseResponse)
async def parse_repo_async(req: ParseRequest) -> AsyncParseResponse:
    """提交异步解析任务（文档 3.4 节）。

    触发 Celery 任务执行完整流程：克隆 → 解析 → 切分 → 向量化入库。
    返回 task_id，前端通过 WebSocket `/ws/{task_id}` 订阅实时进度。
    """
    from app.core.config import settings
    from app.core.celery_app import parse_repo_task

    url = str(req.repo_url)
    logger.info(f"收到异步解析请求: {url} (branch={req.branch})")

    try:
        async_result = parse_repo_task.delay(url, req.branch, req.max_files)
        task_id = async_result.id
    except Exception as e:
        logger.exception("Celery 任务提交失败")
        raise HTTPException(status_code=503, detail=f"任务队列不可用: {e}") from e

    ws_url = f"ws://{settings.backend_external_host}:{settings.app_port}/api/v1/ws/{task_id}"
    logger.info(f"异步任务已提交: task_id={task_id}")
    return AsyncParseResponse(
        task_id=task_id,
        repo_url=url,
        status="queued",
        ws_url=ws_url,
    )


@router.get("/parse-async/{task_id}/status")
async def get_async_parse_status(task_id: str) -> dict:
    """查询异步解析任务状态。"""
    from app.core.celery_app import celery_app
    from celery.result import AsyncResult

    result = AsyncResult(task_id, app=celery_app)
    state = result.state
    info = result.info if result.info else {}

    response = {
        "task_id": task_id,
        "state": state,
        "info": info if isinstance(info, dict) else {"detail": str(info)},
    }
    if state == "SUCCESS":
        response["result"] = info if isinstance(info, dict) else {}
    elif state == "FAILURE":
        response["error"] = str(info)
    return response
