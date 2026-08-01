"""Qdrant 向量数据库服务封装。

阶段一职责：
- 初始化代码块 / 文档两个集合（含 HNSW 索引配置）
- 提供集合列表查询（用于连通性检查）
阶段二将补充 upsert / search 等方法。
"""

from __future__ import annotations

from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.http.models import (
    Distance,
    HnswConfigDiff,
    VectorParams,
)

from app.core.config import settings


class QdrantService:
    """Qdrant 客户端单例封装。"""

    def __init__(self) -> None:
        self._client: QdrantClient | None = None

    @property
    def client(self) -> QdrantClient:
        if self._client is None:
            self._client = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key or None,
                timeout=30,
            )
        return self._client

    def ensure_collection(self, name: str, vector_size: int) -> bool:
        """确保集合存在；若不存在则创建。返回是否新建。"""
        try:
            self.client.get_collection(name)
            return False
        except (UnexpectedResponse, Exception):  # noqa: BLE001
            logger.info(f"创建 Qdrant 集合: {name} (dim={vector_size})")
            self.client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
                hnsw_config=HnswConfigDiff(m=16, ef_construct=100),
            )
            return True

    def init_all(self) -> None:
        """初始化所有业务集合。"""
        self.ensure_collection(settings.qdrant_collection_code, settings.qdrant_vector_size)
        self.ensure_collection(settings.qdrant_collection_docs, settings.qdrant_vector_size)
        logger.info("Qdrant 集合初始化完成")

    def list_collections(self) -> list[str]:
        resp = self.client.get_collections()
        return [c.name for c in resp.collections]

    def ping(self) -> bool:
        """连通性探测。"""
        try:
            self.client.get_collections()
            return True
        except Exception:  # noqa: BLE001
            return False


qdrant_service = QdrantService()
