"""系统健康与连通性检查接口。

用于验证阶段一「数据服务间的网络连通性」完成标准。
"""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.services.minio_service import minio_service
from app.services.qdrant_service import qdrant_service

router = APIRouter()


@router.get("/health/live")
async def live() -> dict:
    """存活探针。"""
    return {"status": "alive"}


@router.get("/health/ready")
async def ready() -> dict:
    """就绪检查：探测所有数据服务连通性。"""
    checks: dict[str, dict] = {}

    # PostgreSQL
    try:
        from app.core.database import SessionLocal

        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        checks["postgres"] = {"status": "ok"}
    except Exception as e:  # noqa: BLE001
        checks["postgres"] = {"status": "error", "detail": str(e)}

    # Redis
    try:
        import redis as _redis

        from app.core.config import settings

        r = _redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password or None,
            db=settings.redis_db,
            socket_connect_timeout=3,
        )
        r.ping()
        checks["redis"] = {"status": "ok"}
    except Exception as e:  # noqa: BLE001
        checks["redis"] = {"status": "error", "detail": str(e)}

    # Qdrant
    try:
        collections = qdrant_service.list_collections()
        checks["qdrant"] = {"status": "ok", "collections": collections}
    except Exception as e:  # noqa: BLE001
        checks["qdrant"] = {"status": "error", "detail": str(e)}

    # MinIO
    try:
        buckets = minio_service.list_buckets()
        checks["minio"] = {"status": "ok", "buckets": buckets}
    except Exception as e:  # noqa: BLE001
        checks["minio"] = {"status": "error", "detail": str(e)}

    all_ok = all(c.get("status") == "ok" for c in checks.values())
    return {"status": "ok" if all_ok else "degraded", "checks": checks}
