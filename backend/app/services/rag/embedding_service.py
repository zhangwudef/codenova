"""Embedding 向量化服务。

提供文本向量化功能，支持多种 Embedding 模型，
与 LangChain 接口兼容，可直接对接 RAG 问答链。
"""

from __future__ import annotations

from loguru import logger

from app.core.config import settings


class EmbeddingService:
    """Embedding 向量化服务。

    封装 HuggingFace Embedding 模型加载与推理，
    提供单条/批量文本向量化接口。
    """

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.embedding_model
        self._model = None
        self._dimension = None

    @property
    def dimension(self) -> int:
        """获取向量维度。"""
        if self._dimension is None:
            self._dimension = self._get_embedding_model().get_sentence_embedding_dimension()
        return self._dimension

    def _get_embedding_model(self):
        """懒加载 Embedding 模型。"""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                logger.info(f"加载 Embedding 模型: {self.model_name}")
                self._model = SentenceTransformer(self.model_name)
                self._dimension = self._model.get_sentence_embedding_dimension()
                logger.info(f"Embedding 模型加载完成, 维度: {self._dimension}")
            except ImportError:
                logger.error("未安装 sentence-transformers，请执行 pip install sentence-transformers")
                raise
            except Exception as e:
                logger.error(f"加载 Embedding 模型失败: {e}")
                raise
        return self._model

    def embed_text(self, text: str) -> list[float]:
        """单条文本向量化。"""
        model = self._get_embedding_model()
        try:
            embedding = model.encode(
                text,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return embedding.tolist()
        except Exception as e:
            logger.error(f"文本向量化失败: {e}")
            raise

    def embed_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """批量文本向量化。"""
        model = self._get_embedding_model()
        try:
            embeddings = model.encode(
                texts,
                batch_size=batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"批量向量化失败: {e}")
            raise

    def embed_query(self, query: str) -> list[float]:
        """查询文本向量化（带查询前缀优化）。"""
        return self.embed_text(query)


class LangChainEmbeddingAdapter:
    """LangChain Embedding 适配器。

    将 EmbeddingService 适配为 LangChain 兼容的 Embeddings 接口，
    可直接用于 QdrantVectorStore 等 LangChain 组件。
    """

    def __init__(self, embedding_service: EmbeddingService | None = None) -> None:
        self.embedding_service = embedding_service or EmbeddingService()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """文档批量向量化（LangChain 接口）。"""
        return self.embedding_service.embed_batch(texts)

    def embed_query(self, text: str) -> list[float]:
        """查询向量化（LangChain 接口）。"""
        return self.embedding_service.embed_query(text)


class MockEmbeddingService:
    """Mock Embedding 服务（用于测试）。

    生成固定维度的随机向量，便于开发和测试阶段使用。
    """

    def __init__(self, dimension: int = 1024) -> None:
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_text(self, text: str) -> list[float]:
        import hashlib

        hash_bytes = hashlib.sha256(text.encode()).digest()
        vector = []
        for i in range(self._dimension):
            idx = i % len(hash_bytes)
            val = hash_bytes[idx] / 255.0
            vector.append(val)
        return vector

    def embed_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        return [self.embed_text(text) for text in texts]

    def embed_query(self, query: str) -> list[float]:
        return self.embed_text(query)


def get_embedding_service(use_mock: bool = False) -> EmbeddingService | MockEmbeddingService:
    """获取 Embedding 服务实例。"""
    if use_mock:
        return MockEmbeddingService(dimension=settings.qdrant_vector_size)
    return EmbeddingService(model_name=settings.embedding_model)
