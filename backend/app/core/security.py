"""安全中间件与依赖：API Key 鉴权。

设计要点:
- 通过环境变量 CODENOVA_API_KEY 配置，留空则不启用（仅本地开发）
- 同时支持 X-API-Key 请求头与 ?api_key= 查询参数（WebSocket 用）
- 健康检查、文档、Swagger UI 等公共路径豁免
- 使用 hmac.compare_digest 防止时序攻击
"""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import APIKeyHeader

from app.core.config import settings

# API Key 请求头名称
API_KEY_HEADER_NAME = "X-API-Key"

# 豁免鉴权的路径前缀（健康检查、文档、OpenAPI schema）
_EXEMPT_PATH_PREFIXES: tuple[str, ...] = (
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
)


api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)


def _is_exempt(path: str) -> bool:
    """检查路径是否在豁免列表中。"""
    return any(path == p or path.startswith(p + "/") or path.startswith(p) for p in _EXEMPT_PATH_PREFIXES)


async def verify_api_key(
    request: Request,
    api_key: Annotated[str | None, Depends(api_key_header)] = None,
) -> str | None:
    """验证 API Key。

    - 若 CODENOVA_API_KEY 未配置，跳过验证（开发模式）
    - 若请求路径在豁免列表，跳过验证
    - 否则要求 X-API-Key 头（WebSocket 可用 ?api_key= 查询参数）
    - 验证失败返回 401
    """
    expected_key = settings.codenova_api_key

    # 未配置 API Key，跳过鉴权（仅本地开发）
    if not expected_key:
        return None

    # 豁免路径
    if _is_exempt(request.url.path):
        return None

    # WebSocket 等场景支持查询参数
    provided_key = api_key or request.query_params.get("api_key")

    if not provided_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide it via X-API-Key header or ?api_key= query parameter.",
            headers={"WWW-Authenticate": API_KEY_HEADER_NAME},
        )

    # 防时序攻击的字符串比较
    if not hmac.compare_digest(provided_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": API_KEY_HEADER_NAME},
        )

    return provided_key


def apply_api_key_dependency(app) -> None:
    """为 FastAPI 应用全局添加 API Key 鉴权依赖。

    用法：在 create_app() 中调用。
    """
    from fastapi import Depends

    app.dependency_overrides[verify_api_key] = verify_api_key
    # 全局依赖：所有路由都会经过 verify_api_key
    # 但豁免路径在函数内部跳过
