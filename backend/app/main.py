"""FastAPI 应用入口。

阶段一提供：
- 健康检查 / 健康探针
- 服务连通性检查接口
- 仓库解析触发接口（同步预览版，阶段二迁移至 Celery 异步任务）
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.api.v1 import api_router
from app.core.config import settings
from app.core.security import verify_api_key


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时记录、退出时清理。"""
    logger.info(f"CodeNova 后端启动中... 环境={settings.app_env}")
    logger.info(f"已配置语言解析器: {', '.join(settings.supported_languages)}")
    if settings.codenova_api_key:
        logger.info("API Key 鉴权已启用")
    else:
        logger.warning("⚠️ API Key 鉴权未启用（仅本地开发应使用此模式）")
    yield
    logger.info("CodeNova 后端关闭。")


def create_app() -> FastAPI:
    app = FastAPI(
        title="CodeNova 智码星 API",
        description="AI 驱动的代码理解与文档自动化平台",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS：通过 CORS_ALLOWED_ORIGINS 环境变量配置
    # allow_credentials=True 时 allow_origins 不能为 ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 全局 API Key 鉴权（豁免路径在 verify_api_key 内部判断）
    app.include_router(
        api_router,
        prefix=settings.api_v1_prefix,
        dependencies=[Depends(verify_api_key)],
    )

    @app.get("/health", tags=["系统"])
    async def health() -> dict:
        """轻量健康探针（不依赖外部服务，豁免鉴权）。"""
        return {"status": "ok", "service": "codenova-backend", "version": "0.1.0"}

    return app


app = create_app()
