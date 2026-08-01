"""任务进度发布器（Redis Pub/Sub）。

用途：Celery worker（独立进程）向 FastAPI 进程的 WebSocket 客户端推送进度。
架构：
  Celery task --publish--> Redis channel --subscribe--> FastAPI WS endpoint --forward--> 浏览器

为什么不直接调用 connection_manager：
  docker-compose 中 celery-worker 与 backend 是不同容器，内存不共享，
  必须通过 Redis（两者都可访问）中转。
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

from app.core.config import settings


def _channel_name(task_id: str) -> str:
    return f"codenova:task:{task_id}:progress"


def _get_redis():
    """获取 Redis 客户端（惰性创建，Celery worker 与 API 共用）。"""
    import redis

    return redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password or None,
        db=settings.redis_db,
        decode_responses=True,
    )


def publish_progress(
    task_id: str,
    progress: int,
    message: str,
    step: str = "",
    **extra: Any,
) -> None:
    """同步发布进度消息到 Redis（供 Celery 任务调用）。

    Args:
        task_id: 任务 ID
        progress: 进度百分比 0-100
        message: 进度描述
        step: 当前步骤标识 clone/parse/split/vectorize/index/complete
        **extra: 额外字段
    """
    payload = {
        "type": "progress",
        "task_id": task_id,
        "progress": progress,
        "message": message,
        "step": step,
    }
    payload.update(extra)
    try:
        client = _get_redis()
        client.publish(_channel_name(task_id), json.dumps(payload, ensure_ascii=False))
    except Exception as e:  # noqa: BLE001 - 进度推送失败不应中断主流程
        logger.warning(f"进度推送失败 (task={task_id}): {e}")


def publish_status(
    task_id: str,
    status: str,
    message: str,
    **extra: Any,
) -> None:
    """同步发布状态变更到 Redis。

    Args:
        task_id: 任务 ID
        status: 状态标识 running/completed/error
        message: 状态描述
        **extra: 额外字段（如 result 摘要、error 详情）
    """
    payload = {
        "type": "status",
        "task_id": task_id,
        "status": status,
        "message": message,
    }
    payload.update(extra)
    try:
        client = _get_redis()
        client.publish(_channel_name(task_id), json.dumps(payload, ensure_ascii=False))
    except Exception as e:  # noqa: BLE001
        logger.warning(f"状态推送失败 (task={task_id}): {e}")


def publish_error(task_id: str, error: str) -> None:
    """发布错误消息。"""
    publish_status(task_id, status="error", message=error, error=error)
