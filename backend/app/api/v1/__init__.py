"""API v1 路由聚合。"""

from fastapi import APIRouter

from app.api.v1 import graph, health, rag, repos, ws

api_router = APIRouter()
api_router.include_router(health.router, tags=["系统"])
api_router.include_router(repos.router, prefix="/repos", tags=["仓库解析"])
api_router.include_router(graph.router, prefix="/repos", tags=["依赖图与时序图"])
api_router.include_router(rag.router, prefix="/rag", tags=["RAG问答"])
api_router.include_router(ws.router, tags=["WebSocket"])
