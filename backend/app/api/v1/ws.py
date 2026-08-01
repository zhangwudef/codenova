"""WebSocket 实时推送接口（文档 3.4 节）。

通过 Redis Pub/Sub 桥接 Celery worker 与浏览器：
  Celery task -> Redis channel -> 本端点订阅 -> WebSocket 转发 -> 前端

消息协议：
  - connected:  {"type": "connected", "task_id": "..."}
  - progress:   {"type": "progress", "progress": 50, "message": "...", "step": "parse"}
  - status:     {"type": "status", "status": "completed", "message": "...", "result": {...}}
  - error:      {"type": "status", "status": "error", "message": "..."}
"""

from __future__ import annotations

import asyncio
import json

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from app.core.config import settings

router = APIRouter()


def _channel_name(task_id: str) -> str:
    return f"codenova:task:{task_id}:progress"


async def _redis_pubsub_listener(task_id: str, websocket: WebSocket) -> None:
    """订阅 Redis 频道，将消息转发给 WebSocket 客户端。

    作为后台任务运行，WebSocket 断开时自动退出。
    """
    client = aioredis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password or None,
        db=settings.redis_db,
        decode_responses=True,
    )
    pubsub = client.pubsub()
    await pubsub.subscribe(_channel_name(task_id))
    logger.info(f"Redis 订阅已建立: task_id={task_id}")

    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                payload = json.loads(message["data"])
                await websocket.send_json(payload)
            except WebSocketDisconnect:
                break
            except Exception as e:  # noqa: BLE001
                logger.warning(f"转发消息失败: {e}")
                break
    except asyncio.CancelledError:
        pass
    finally:
        try:
            await pubsub.unsubscribe(_channel_name(task_id))
            await pubsub.close()
            await client.close()
        except Exception:  # noqa: BLE001
            pass
        logger.info(f"Redis 订阅已关闭: task_id={task_id}")


@router.websocket("/ws/{task_id}")
async def websocket_endpoint(websocket: WebSocket, task_id: str) -> None:
    """WebSocket 端点：订阅任务进度推送。

    建立 Redis Pub/Sub 订阅，将 Celery 任务发布的进度/状态消息实时转发给前端。
    同时支持客户端发送 ping/subscribe 控制消息。
    """
    await websocket.accept()

    # 发送连接确认
    await websocket.send_json({
        "type": "connected",
        "task_id": task_id,
        "message": "已连接，等待进度更新...",
    })

    # 启动 Redis 订阅后台任务
    listener_task = asyncio.create_task(_redis_pubsub_listener(task_id, websocket))

    try:
        # 同时监听客户端消息（ping/控制），与 Redis 订阅并行
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                action = msg.get("action", "")
                if action == "ping":
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                logger.warning(f"无效的 JSON 消息: {data}")
    except WebSocketDisconnect:
        logger.info(f"WebSocket 客户端断开: task_id={task_id}")
    except Exception as e:  # noqa: BLE001
        logger.error(f"WebSocket 错误: {e}")
    finally:
        listener_task.cancel()
        try:
            await listener_task
        except asyncio.CancelledError:
            pass


# 保留兼容接口（同进程内调用，现已不作为主路径；Celery 走 Redis Pub/Sub）
async def push_progress(task_id: str, progress: int, message: str, **extra) -> None:
    """推送进度更新（兼容接口，建议使用 app.core.progress_publisher）。"""
    from app.core.progress_publisher import publish_progress

    publish_progress(task_id, progress, message, **extra)


async def push_status(task_id: str, status: str, message: str, **extra) -> None:
    """推送状态变更（兼容接口）。"""
    from app.core.progress_publisher import publish_status

    publish_status(task_id, status, message, **extra)