"""Qdrant 向量存储服务测试。

注意：这些测试需要 Qdrant 服务运行。
可通过环境变量或跳过标记来控制。
"""

import os

import pytest

from app.services.rag.embedding_service import MockEmbeddingService
from app.services.rag.schemas import ChunkType, CodeChunkMetadata


def _is_qdrant_available() -> bool:
    """检查 Qdrant 是否可用。"""
    try:
        from app.services.qdrant_service import qdrant_service
        info = qdrant_service.client.get_collections()
        return True
    except Exception:
        return False


# 跳过标记
requires_qdrant = pytest.mark.skipif(
    not _is_qdrant_available(),
    reason="Qdrant 服务未运行，跳过向量存储集成测试",
)


@pytest.fixture
def sample_chunks():
    """创建示例代码块。"""
    return [
        (
            "def hello():\n    return 'Hello'",
            CodeChunkMetadata(
                file_path="test.py",
                language="python",
                chunk_type=ChunkType.FUNCTION,
                symbol_name="hello",
                start_line=1,
                end_line=3,
            ),
        ),
        (
            "def world():\n    return 'World'",
            CodeChunkMetadata(
                file_path="test2.py",
                language="python",
                chunk_type=ChunkType.FUNCTION,
                symbol_name="world",
                start_line=1,
                end_line=3,
            ),
        ),
    ]


class TestVectorStoreService:
    """向量存储服务测试。"""

    @pytest.fixture
    def mock_embedding(self):
        """Mock Embedding 服务。"""
        return MockEmbeddingService(dimension=1024)

    @requires_qdrant
    def test_build_payload(self, mock_embedding, sample_chunks):
        """测试 payload 构建。"""
        from app.services.rag.vector_store import VectorStoreService

        service = VectorStoreService(embedding_service=mock_embedding)
        content, metadata = sample_chunks[0]
        payload = service._build_payload(content, metadata, "https://github.com/test")

        assert payload["content"] == content
        assert payload["file_path"] == "test.py"
        assert payload["language"] == "python"
        assert payload["chunk_type"] == "function"
        assert payload["repo_url"] == "https://github.com/test"

    @requires_qdrant
    def test_index_code_chunks_with_mock(self, mock_embedding, sample_chunks):
        """使用 Mock 测试索引构建。"""
        from app.services.rag.vector_store import VectorStoreService

        service = VectorStoreService(embedding_service=mock_embedding)
        result = service.index_code_chunks(
            sample_chunks,
            repo_url="https://github.com/test",
            batch_size=2,
        )

        assert result.repo_url == "https://github.com/test"
        assert result.total_chunks == 2
        assert result.total_embeddings == 2
        assert result.elapsed_seconds >= 0

    @requires_qdrant
    def test_count_points(self, mock_embedding, sample_chunks):
        """测试向量计数。"""
        from app.services.rag.vector_store import VectorStoreService

        service = VectorStoreService(embedding_service=mock_embedding)
        initial_count = service.count_points()
        assert isinstance(initial_count, int)

    @requires_qdrant
    def test_search_with_mock(self, mock_embedding, sample_chunks):
        """使用 Mock 测试向量检索。"""
        from app.services.rag.vector_store import VectorStoreService

        service = VectorStoreService(embedding_service=mock_embedding)
        service.index_code_chunks(sample_chunks, repo_url="https://github.com/test")

        results = service.search(
            query="hello function",
            top_k=2,
            repo_url="https://github.com/test",
        )

        assert isinstance(results, list)
        assert len(results) <= 2


class TestVectorStoreIntegration:
    """向量存储集成测试。"""

    @requires_qdrant
    def test_full_index_search_flow(self, sample_chunks):
        """完整的索引-检索流程。"""
        mock_embedding = MockEmbeddingService(dimension=1024)

        from app.services.rag.vector_store import VectorStoreService

        service = VectorStoreService(embedding_service=mock_embedding)

        # 索引
        index_result = service.index_code_chunks(
            sample_chunks,
            repo_url="https://github.com/integration-test",
        )
        assert index_result.total_embeddings == 2

        # 检索
        search_results = service.search(
            query="hello world",
            top_k=5,
            repo_url="https://github.com/integration-test",
        )
        assert isinstance(search_results, list)

    @requires_qdrant
    def test_delete_and_verify(self, sample_chunks):
        """删除数据验证。"""
        mock_embedding = MockEmbeddingService(dimension=1024)

        from app.services.rag.vector_store import VectorStoreService

        service = VectorStoreService(embedding_service=mock_embedding)

        test_repo = "https://github.com/to-delete"
        service.index_code_chunks(sample_chunks, repo_url=test_repo)

        # 删除
        deleted = service.delete_by_repo(test_repo)
        assert isinstance(deleted, int)
