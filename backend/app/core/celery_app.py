"""Celery 任务队列配置与异步解析任务。

对接真实解析流程（文档 3.4 节）：
  克隆 → AST 解析 → 代码切分 → 向量化入库 → 完成
每步通过 Redis Pub/Sub 推送进度，由 FastAPI WebSocket 转发给前端。
"""

from __future__ import annotations

from pathlib import Path

from celery import Celery
from loguru import logger

from app.core.config import settings
from app.core.progress_publisher import publish_error, publish_progress, publish_status

# 创建 Celery 实例
celery_app = Celery(
    "codenova",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# 配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    # 任务超时
    task_time_limit=3600,  # 1小时
    task_soft_time_limit=3540,  # 59分钟（软超时，用于优雅终止）
    # 重试策略
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # 并发
    worker_prefetch_multiplier=1,
)


@celery_app.task(bind=True, name="codenova.parse_repo")
def parse_repo_task(self, repo_url: str, branch: str | None = None, max_files: int = 200) -> dict:
    """异步仓库解析任务（真实流程）。

    步骤：
      1. clone   (0-15%)  克隆仓库
      2. parse   (15-45%) Tree-sitter AST 解析
      3. split   (45-60%) AST 切分为代码块
      4. vectorize (60-90%) Embedding + Qdrant 入库
      5. complete (100%)  完成

    进度通过 Redis Pub/Sub 推送，FastAPI WebSocket 订阅转发给前端。
    """
    task_id = self.request.id
    logger.info(f"Celery 任务开始: {task_id}, repo={repo_url}")
    publish_status(task_id, status="running", message=f"开始解析 {repo_url}", step="init")

    # 延迟导入，避免 Celery worker 启动时强依赖这些服务
    from app.services.github_service import github_service
    from app.services.parser.pipeline import ParsingPipeline
    from app.services.rag.ast_splitter import ASTChunkStrategy
    from app.services.rag.schemas import CodeChunkMetadata, ChunkType
    from app.services.rag.vector_store import VectorStoreService

    local_path: Path | None = None
    try:
        # ---------- 步骤1：克隆 ----------
        publish_progress(task_id, 5, "正在克隆仓库...", step="clone")
        self.update_state(state="PROGRESS", meta={"progress": 5, "step": "clone"})
        local_path = github_service.clone(repo_url, branch=branch)
        publish_progress(task_id, 15, f"克隆完成: {local_path.name}", step="clone")

        # ---------- 步骤2：AST 解析 ----------
        publish_progress(task_id, 20, "正在解析 AST...", step="parse")
        self.update_state(state="PROGRESS", meta={"progress": 20, "step": "parse"})
        pipeline = ParsingPipeline()
        summary = pipeline.run(local_path, repo_url=repo_url, max_files=max_files)
        publish_progress(
            task_id, 45,
            f"解析完成: {summary.parsed_files} 文件, {summary.total_symbols} 符号",
            step="parse",
            total_files=summary.total_files,
            total_symbols=summary.total_symbols,
        )

        # ---------- 步骤3：代码切分 ----------
        publish_progress(task_id, 50, "正在切分代码块...", step="split")
        self.update_state(state="PROGRESS", meta={"progress": 50, "step": "split"})
        strategy = ASTChunkStrategy()
        all_chunks: list[tuple[str, CodeChunkMetadata]] = []
        for file_info in summary.files:
            if file_info.skipped or not file_info.chunks:
                continue
            # 直接复用已解析的 CodeChunk 构造 metadata，避免重复解析
            for chunk in file_info.chunks:
                content = chunk.content
                metadata = CodeChunkMetadata(
                    file_path=chunk.file_path,
                    language=chunk.language,
                    chunk_type=ChunkType(chunk.symbol_type.value) if chunk.symbol_type.value in ChunkType._value2member_map_ else ChunkType.FUNCTION,
                    symbol_name=chunk.symbol_name,
                    qualified_name=chunk.qualified_name,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    repo_url=repo_url,
                )
                all_chunks.append((content, metadata))
        publish_progress(
            task_id, 60,
            f"切分完成: {len(all_chunks)} 代码块",
            step="split",
            total_chunks=len(all_chunks),
        )

        # ---------- 步骤4：向量化入库 ----------
        publish_progress(task_id, 65, "正在生成 Embedding 并入库 Qdrant...", step="vectorize")
        self.update_state(state="PROGRESS", meta={"progress": 65, "step": "vectorize"})
        indexed = 0
        if all_chunks:
            try:
                vs = VectorStoreService()
                index_result = vs.index_code_chunks(all_chunks, repo_url=repo_url, batch_size=32)
                indexed = index_result.total_embeddings
                publish_progress(
                    task_id, 90,
                    f"入库完成: {indexed} 向量",
                    step="vectorize",
                    indexed_count=indexed,
                )
            except Exception as e:  # noqa: BLE001 - 向量化失败不阻塞整体，降级为仅解析
                logger.warning(f"向量化入库失败（降级为仅解析）: {e}")
                publish_progress(
                    task_id, 90,
                    f"向量化跳过: {e}",
                    step="vectorize",
                    indexed_count=0,
                )
        else:
            publish_progress(task_id, 90, "无代码块需要入库", step="vectorize", indexed_count=0)

        # ---------- 步骤5：完成 ----------
        elapsed = summary.elapsed_seconds
        result = {
            "task_id": task_id,
            "repo_url": repo_url,
            "status": "completed",
            "message": "解析完成",
            "total_files": summary.total_files,
            "parsed_files": summary.parsed_files,
            "total_symbols": summary.total_symbols,
            "total_chunks": len(all_chunks),
            "indexed_count": indexed,
            "elapsed_seconds": elapsed,
        }
        publish_status(
            task_id, status="completed",
            message=f"解析完成: {summary.parsed_files} 文件 / {len(all_chunks)} 块 / {indexed} 向量",
            step="complete",
            result=result,
        )
        self.update_state(state="SUCCESS", meta=result)
        logger.info(f"Celery 任务完成: {task_id}, result={result}")
        return result

    except Exception as e:  # noqa: BLE001 - Celery 任务执行容错
        logger.error(f"Celery 任务失败: {task_id}, error={e}")
        publish_error(task_id, f"解析失败: {e}")
        # 重试 3 次，间隔 60s
        raise self.retry(exc=e, countdown=60, max_retries=3)
    finally:
        if local_path is not None:
            try:
                github_service.cleanup(local_path)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"清理临时目录失败: {e}")


@celery_app.task(name="codenova.health_check")
def health_check_task() -> dict:
    """Celery 健康检查任务。"""
    return {
        "status": "ok",
        "celery": "running",
        "broker": settings.celery_broker_url,
    }