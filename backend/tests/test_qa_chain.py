"""RAG 问答链测试。"""

import pytest

from app.services.rag.embedding_service import MockEmbeddingService
from app.services.rag.qa_chain import RAGChain
from app.services.rag.schemas import (
    ChunkType,
    CodeChunkMetadata,
    QAAnswer,
    QAQuestion,
    RetrievedChunk,
)


def _is_qdrant_available() -> bool:
    """检查 Qdrant 是否可用。"""
    try:
        from app.services.qdrant_service import qdrant_service
        qdrant_service.client.get_collections()
        return True
    except Exception:
        return False


requires_qdrant = pytest.mark.skipif(
    not _is_qdrant_available(),
    reason="Qdrant 服务未运行，跳过集成测试",
)


@pytest.fixture
def mock_embedding():
    """Mock Embedding 服务。"""
    return MockEmbeddingService(dimension=1024)


@pytest.fixture
def sample_retrieved_chunks():
    """创建示例检索结果。"""
    return [
        RetrievedChunk(
            content="def hello():\n    return 'Hello, World!'",
            metadata=CodeChunkMetadata(
                file_path="test.py",
                language="python",
                chunk_type=ChunkType.FUNCTION,
                symbol_name="hello",
                start_line=1,
                end_line=3,
            ),
            score=0.95,
        ),
        RetrievedChunk(
            content="class TestClass:\n    pass",
            metadata=CodeChunkMetadata(
                file_path="test.py",
                language="python",
                chunk_type=ChunkType.CLASS,
                symbol_name="TestClass",
                start_line=5,
                end_line=6,
            ),
            score=0.85,
        ),
    ]


class TestRAGChain:
    """RAG 问答链单元测试。"""

    def test_build_context(self, mock_embedding, sample_retrieved_chunks):
        """测试上下文构建。"""
        chain = RAGChain()
        context = chain._build_context(sample_retrieved_chunks)

        assert "test.py" in context
        assert "hello" in context
        assert "TestClass" in context

    def test_format_source_summary(self, mock_embedding, sample_retrieved_chunks):
        """测试来源摘要格式化。"""
        chain = RAGChain()
        summary = chain._format_source_summary(sample_retrieved_chunks)

        assert "test.py" in summary
        assert "hello" in summary

    def test_generate_fallback_answer(self, mock_embedding, sample_retrieved_chunks):
        """测试降级答案生成。"""
        chain = RAGChain()
        answer = chain._generate_fallback_answer(
            "What is the hello function?",
            sample_retrieved_chunks,
        )

        assert "hello" in answer
        assert "test.py" in answer

    def test_qa_question_model(self):
        """测试问答请求模型。"""
        question = QAQuestion(
            question="How does hello() work?",
            repo_url="https://github.com/test",
            top_k=3,
        )
        assert question.question == "How does hello() work?"
        assert question.top_k == 3

    def test_qa_answer_model(self):
        """测试问答响应模型。"""
        sources = [
            RetrievedChunk(
                content="test content",
                metadata=CodeChunkMetadata(
                    file_path="test.py",
                    language="python",
                    chunk_type=ChunkType.FUNCTION,
                ),
                score=0.9,
            )
        ]
        answer = QAAnswer(
            answer="This is the answer.",
            sources=sources,
            question="test question",
            model="test-model",
            latency_ms=100.0,
        )
        assert answer.answer == "This is the answer."
        assert len(answer.sources) == 1
        assert answer.model == "test-model"


class TestRAGChainIntegration:
    """RAG 问答链集成测试（需要 Qdrant）。"""

    @requires_qdrant
    def test_ask_with_no_results(self, mock_embedding):
        """测试无检索结果的问答。"""
        from app.services.rag.vector_store import VectorStoreService

        vector_store = VectorStoreService(embedding_service=mock_embedding)
        chain = RAGChain(vector_store=vector_store)

        question = QAQuestion(
            question="Nonexistent function",
            repo_url="https://github.com/nonexistent",
        )

        answer = chain.ask(question)

        assert answer.answer is not None
        assert len(answer.sources) == 0

    @requires_qdrant
    def test_ask_with_results(self, mock_embedding):
        """测试有检索结果的问答（降级模式）。"""
        from app.services.rag.vector_store import VectorStoreService
        from app.services.rag.schemas import ChunkType, CodeChunkMetadata

        vector_store = VectorStoreService(embedding_service=mock_embedding)

        # 先索引一些数据
        chunks = [
            (
                "def important_function():\n    '''Important doc.'''\n    return 42",
                CodeChunkMetadata(
                    file_path="important.py",
                    language="python",
                    chunk_type=ChunkType.FUNCTION,
                    symbol_name="important_function",
                    start_line=1,
                    end_line=3,
                ),
            )
        ]
        vector_store.index_code_chunks(chunks, repo_url="https://github.com/test-qa")

        chain = RAGChain(vector_store=vector_store)

        question = QAQuestion(
            question="What does important_function do?",
            repo_url="https://github.com/test-qa",
        )

        answer = chain.ask(question)

        assert answer.answer is not None
        assert answer.question == question.question
        assert answer.latency_ms >= 0
