"""Embedding 服务单元测试。"""

import pytest

from app.services.rag.embedding_service import (
    MockEmbeddingService,
    get_embedding_service,
)


class TestMockEmbeddingService:
    """Mock Embedding 服务测试。"""

    def test_init_with_default_dimension(self):
        """默认维度初始化。"""
        service = MockEmbeddingService()
        assert service.dimension == 1024

    def test_init_with_custom_dimension(self):
        """自定义维度初始化。"""
        service = MockEmbeddingService(dimension=512)
        assert service.dimension == 512

    def test_embed_text_returns_correct_dimension(self):
        """单文本向量化返回正确维度。"""
        service = MockEmbeddingService(dimension=256)
        result = service.embed_text("test text")
        assert len(result) == 256

    def test_embed_text_deterministic(self):
        """相同文本产生相同向量。"""
        service = MockEmbeddingService(dimension=128)
        result1 = service.embed_text("test")
        result2 = service.embed_text("test")
        assert result1 == result2

    def test_embed_different_texts_different_vectors(self):
        """不同文本产生不同向量。"""
        service = MockEmbeddingService(dimension=128)
        result1 = service.embed_text("text1")
        result2 = service.embed_text("text2")
        assert result1 != result2

    def test_embed_batch(self):
        """批量向量化。"""
        service = MockEmbeddingService(dimension=64)
        texts = ["text1", "text2", "text3"]
        results = service.embed_batch(texts)
        assert len(results) == 3
        for result in results:
            assert len(result) == 64

    def test_embed_query(self):
        """查询向量化。"""
        service = MockEmbeddingService(dimension=128)
        result = service.embed_query("query text")
        assert len(result) == 128

    def test_embed_query_matches_embed_text(self):
        """查询向量化与文本向量化一致。"""
        service = MockEmbeddingService(dimension=128)
        text = "same text"
        query_result = service.embed_query(text)
        text_result = service.embed_text(text)
        assert query_result == text_result


class TestGetEmbeddingService:
    """获取服务实例测试。"""

    def test_get_mock_service(self):
        """获取 Mock 服务。"""
        service = get_embedding_service(use_mock=True)
        assert isinstance(service, MockEmbeddingService)

    def test_mock_service_dimension(self):
        """Mock 服务维度配置。"""
        from app.core.config import settings
        service = get_embedding_service(use_mock=True)
        assert service.dimension == settings.qdrant_vector_size


class TestEmbeddingServiceIntegration:
    """Embedding 集成测试（使用 Mock）。"""

    def test_batch_processing_consistency(self):
        """批量处理一致性。"""
        service = MockEmbeddingService(dimension=128)
        texts = ["text1", "text2"]
        batch_results = service.embed_batch(texts)
        individual_results = [service.embed_text(t) for t in texts]
        assert batch_results == individual_results

    def test_empty_batch(self):
        """空批量处理。"""
        service = MockEmbeddingService(dimension=64)
        results = service.embed_batch([])
        assert results == []

    def test_single_text_batch(self):
        """单文本批量处理。"""
        service = MockEmbeddingService(dimension=64)
        results = service.embed_batch(["single"])
        assert len(results) == 1
        assert len(results[0]) == 64
