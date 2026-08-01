"""Qdrant 向量存储服务。

实现向量数据的存储、检索和索引管理，
与 LangChain QdrantVectorStore 集成。
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from loguru import logger
from qdrant_client.http.models import (
    FieldCondition,
    Filter,
    MatchAny,
)

from app.core.config import settings
from app.services.qdrant_service import qdrant_service
from app.services.rag.embedding_service import (
    EmbeddingService,
    LangChainEmbeddingAdapter,
    get_embedding_service,
)
from app.services.rag.schemas import (
    CodeChunkMetadata,
    IndexResult,
    RetrievedChunk,
)


class VectorStoreService:
    """向量存储服务。

    管理代码块和文档的向量化存储，提供索引构建、
    向量检索等核心功能。
    """

    def __init__(self, embedding_service: EmbeddingService | None = None) -> None:
        self.embedding_service = embedding_service or get_embedding_service()
        self.qdrant = qdrant_service
        self._ensure_collections()

    def _ensure_collections(self) -> None:
        """确保集合存在。"""
        self.qdrant.ensure_collection(
            settings.qdrant_collection_code,
            self.embedding_service.dimension,
        )
        self.qdrant.ensure_collection(
            settings.qdrant_collection_docs,
            self.embedding_service.dimension,
        )

    def index_code_chunks(
        self,
        chunks: list[tuple[str, CodeChunkMetadata]],
        repo_url: str = "",
        batch_size: int = 32,
    ) -> IndexResult:
        """将代码块批量导入向量数据库。

        Args:
            chunks: [(content, metadata), ...] 列表
            repo_url: 仓库地址
            batch_size: 批量处理大小

        Returns:
            索引构建结果
        """
        start_time = time.perf_counter()
        content_list = [chunk[0] for chunk in chunks]
        metadata_list = [chunk[1] for chunk in chunks]

        total_embedded = 0

        for i in range(0, len(content_list), batch_size):
            batch_contents = content_list[i:i + batch_size]
            batch_metadata = metadata_list[i:i + batch_size]

            try:
                embeddings = self.embedding_service.embed_batch(batch_contents)
            except Exception as e:  # noqa: BLE001 - 外部 Embedding 服务调用容错
                logger.error(f"批量向量化失败 (batch {i // batch_size}): {e}")
                continue

            points = []
            for j, (content, metadata, vector) in enumerate(
                zip(batch_contents, batch_metadata, embeddings)
            ):
                point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{repo_url}/{metadata.file_path}/{i + j}"))
                payload = self._build_payload(content, metadata, repo_url)
                points.append({
                    "id": point_id,
                    "vector": vector,
                    "payload": payload,
                })

            try:
                self.qdrant.client.upsert(
                    collection_name=settings.qdrant_collection_code,
                    points=points,
                )
                total_embedded += len(points)
            except Exception as e:  # noqa: BLE001 - Qdrant 服务调用容错
                logger.error(f"向量入库失败 (batch {i // batch_size}): {e}")

        elapsed = time.perf_counter() - start_time

        result = IndexResult(
            repo_url=repo_url,
            total_files=len({m.file_path for m in metadata_list}),
            total_chunks=len(chunks),
            total_embeddings=total_embedded,
            collection_name=settings.qdrant_collection_code,
            elapsed_seconds=elapsed,
        )

        logger.info(
            f"索引构建完成: {result.total_chunks} chunks, "
            f"{total_embedded} embedded, {elapsed:.2f}s"
        )
        return result

    def search(
        self,
        query: str,
        collection_name: str | None = None,
        top_k: int = 5,
        score_threshold: float = 0.5,
        repo_url: str | None = None,
    ) -> list[RetrievedChunk]:
        """向量检索。

        Args:
            query: 查询文本
            collection_name: 集合名称
            top_k: 返回结果数量
            score_threshold: 最低分数阈值
            repo_url: 限定仓库URL

        Returns:
            检索到的代码块列表
        """
        collection = collection_name or settings.qdrant_collection_code

        try:
            query_vector = self.embedding_service.embed_query(query)
        except Exception as e:  # noqa: BLE001 - Embedding 服务调用容错
            logger.error(f"查询向量化失败: {e}")
            return []

        search_filter = None
        if repo_url:
            search_filter = Filter(
                must=[
                    FieldCondition(
                        key="repo_url",
                        match=MatchAny(any=[repo_url]),
                    )
                ]
            )

        try:
            results = self.qdrant.client.search(
                collection_name=collection,
                query_vector=query_vector,
                limit=top_k * 2,
                query_filter=search_filter,
                score_threshold=score_threshold,
            )
        except Exception as e:  # noqa: BLE001 - Qdrant 检索服务容错
            logger.error(f"向量检索失败: {e}")
            return []

        retrieved_chunks: list[RetrievedChunk] = []
        for point in results:
            payload = point.payload or {}
            metadata = CodeChunkMetadata(
                file_path=payload.get("file_path", ""),
                language=payload.get("language", "unknown"),
                chunk_type=payload.get("chunk_type", "plain_text"),
                symbol_name=payload.get("symbol_name"),
                qualified_name=payload.get("qualified_name"),
                start_line=payload.get("start_line"),
                end_line=payload.get("end_line"),
                repo_url=payload.get("repo_url"),
                extra=payload.get("extra", {}),
            )

            chunk = RetrievedChunk(
                content=payload.get("content", ""),
                metadata=metadata,
                score=point.score,
            )
            retrieved_chunks.append(chunk)

            if len(retrieved_chunks) >= top_k:
                break

        logger.info(f"向量检索完成: query='{query[:50]}...' -> {len(retrieved_chunks)} 结果")
        return retrieved_chunks

    def delete_by_repo(self, repo_url: str, collection_name: str | None = None) -> int:
        """删除指定仓库的所有向量数据。

        Returns:
            删除前匹配的向量数量（Qdrant delete 不直接返回删除数，需先查询）
        """
        collection = collection_name or settings.qdrant_collection_code

        try:
            # 先查询匹配数量
            search_filter = Filter(
                must=[
                    FieldCondition(
                        key="repo_url",
                        match=MatchAny(any=[repo_url]),
                    )
                ]
            )
            count_result = self.qdrant.client.count(
                collection_name=collection,
                query_filter=search_filter,
            )
            before_count = count_result.count

            if before_count == 0:
                logger.info(f"仓库 {repo_url} 无匹配向量，跳过删除")
                return 0

            # 执行删除
            self.qdrant.client.delete(
                collection_name=collection,
                points_selector=search_filter,
            )
            logger.info(f"删除仓库向量数据: {repo_url} -> 删除前数量={before_count}")
            return before_count
        except Exception as e:  # noqa: BLE001 - Qdrant 删除服务容错
            logger.error(f"删除向量数据失败: {e}")
            return 0

    def count_points(self, collection_name: str | None = None) -> int:
        """统计集合中的向量数量。"""
        collection = collection_name or settings.qdrant_collection_code
        try:
            info = self.qdrant.client.count(collection_name=collection)
            return info.count
        except Exception:  # noqa: BLE001 - Qdrant 计数服务容错
            return 0

    def _build_payload(
        self, content: str, metadata: CodeChunkMetadata, repo_url: str
    ) -> dict[str, Any]:
        """构建 Qdrant payload。"""
        return {
            "content": content,
            "file_path": metadata.file_path,
            "language": metadata.language,
            "chunk_type": metadata.chunk_type.value,
            "symbol_name": metadata.symbol_name,
            "qualified_name": metadata.qualified_name,
            "start_line": metadata.start_line,
            "end_line": metadata.end_line,
            "repo_url": repo_url,
            "extra": metadata.extra,
        }


_langchain_vector_store = None


def get_langchain_vector_store():
    """获取 LangChain 兼容的向量存储实例。"""
    global _langchain_vector_store
    if _langchain_vector_store is None:
        try:
            from langchain_qdrant import QdrantVectorStore

            embedding_adapter = LangChainEmbeddingAdapter(get_embedding_service())

            _langchain_vector_store = QdrantVectorStore(
                client=qdrant_service.client,
                collection_name=settings.qdrant_collection_code,
                embedding=embedding_adapter,
                vector_name="",
            )
            logger.info("LangChain QdrantVectorStore 初始化完成")
        except Exception as e:
            logger.error(f"LangChain QdrantVectorStore 初始化失败: {e}")
            raise
    return _langchain_vector_store
