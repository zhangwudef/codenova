"""RAG 模块 - 检索增强生成。

包含代码切分、向量化、向量存储、问答链和文档生成等核心功能。
采用惰性导入以避免不必要的依赖加载。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.rag.ast_splitter import (
        ASTChunkStrategy,
        BaseChunkStrategy,
        ChunkStrategyFactory,
        CodeSplitter,
        FixedLengthChunkStrategy,
        SemanticChunkStrategy,
    )
    from app.services.rag.embedding_service import (
        EmbeddingService,
        LangChainEmbeddingAdapter,
        MockEmbeddingService,
        get_embedding_service,
    )
    from app.services.rag.prompts import (
        APIDocTemplate,
        BaseDocTemplate,
        DocTemplateFactory,
        ModuleDocTemplate,
        ReadmeDocTemplate,
        generate_document,
    )
    from app.services.rag.qa_chain import RAGChain, SimpleRAGService
    from app.services.rag.schemas import (
        ChunkType,
        CodeChunkMetadata,
        DocGenerateRequest,
        DocGenerateResult,
        DocType,
        IndexRequest,
        IndexResult,
        QAAnswer,
        QAQuestion,
        RetrievedChunk,
        VectorRecord,
    )
    from app.services.rag.vector_store import (
        VectorStoreService,
        get_langchain_vector_store,
    )


def __getattr__(name: str):
    """惰性导入实现。"""
    _schemas = {
        "ChunkType", "CodeChunkMetadata", "DocGenerateRequest",
        "DocGenerateResult", "DocType", "IndexRequest", "IndexResult",
        "QAAnswer", "QAQuestion", "RetrievedChunk", "VectorRecord",
    }
    _ast = {
        "ASTChunkStrategy", "BaseChunkStrategy", "ChunkStrategyFactory",
        "CodeSplitter", "FixedLengthChunkStrategy", "SemanticChunkStrategy",
    }
    _embedding = {
        "EmbeddingService", "LangChainEmbeddingAdapter",
        "MockEmbeddingService", "get_embedding_service",
    }
    _vector = {"VectorStoreService", "get_langchain_vector_store"}
    _chain = {"RAGChain", "SimpleRAGService"}
    _prompts = {
        "APIDocTemplate", "BaseDocTemplate", "DocTemplateFactory",
        "ModuleDocTemplate", "ReadmeDocTemplate", "generate_document",
    }

    if name in _schemas:
        from app.services.rag.schemas import (
            ChunkType,
            CodeChunkMetadata,
            DocGenerateRequest,
            DocGenerateResult,
            DocType,
            IndexRequest,
            IndexResult,
            QAAnswer,
            QAQuestion,
            RetrievedChunk,
            VectorRecord,
        )
        mapping = {
            "ChunkType": ChunkType, "CodeChunkMetadata": CodeChunkMetadata,
            "DocGenerateRequest": DocGenerateRequest,
            "DocGenerateResult": DocGenerateResult, "DocType": DocType,
            "IndexRequest": IndexRequest, "IndexResult": IndexResult,
            "QAAnswer": QAAnswer, "QAQuestion": QAQuestion,
            "RetrievedChunk": RetrievedChunk, "VectorRecord": VectorRecord,
        }
        return mapping[name]

    if name in _ast:
        from app.services.rag.ast_splitter import (
            ASTChunkStrategy,
            BaseChunkStrategy,
            ChunkStrategyFactory,
            CodeSplitter,
            FixedLengthChunkStrategy,
            SemanticChunkStrategy,
        )
        mapping = {
            "ASTChunkStrategy": ASTChunkStrategy,
            "BaseChunkStrategy": BaseChunkStrategy,
            "ChunkStrategyFactory": ChunkStrategyFactory,
            "CodeSplitter": CodeSplitter,
            "FixedLengthChunkStrategy": FixedLengthChunkStrategy,
            "SemanticChunkStrategy": SemanticChunkStrategy,
        }
        return mapping[name]

    if name in _embedding:
        from app.services.rag.embedding_service import (
            EmbeddingService,
            LangChainEmbeddingAdapter,
            MockEmbeddingService,
            get_embedding_service,
        )
        mapping = {
            "EmbeddingService": EmbeddingService,
            "LangChainEmbeddingAdapter": LangChainEmbeddingAdapter,
            "MockEmbeddingService": MockEmbeddingService,
            "get_embedding_service": get_embedding_service,
        }
        return mapping[name]

    if name in _vector:
        from app.services.rag.vector_store import (
            VectorStoreService,
            get_langchain_vector_store,
        )
        mapping = {
            "VectorStoreService": VectorStoreService,
            "get_langchain_vector_store": get_langchain_vector_store,
        }
        return mapping[name]

    if name in _chain:
        from app.services.rag.qa_chain import RAGChain, SimpleRAGService
        mapping = {"RAGChain": RAGChain, "SimpleRAGService": SimpleRAGService}
        return mapping[name]

    if name in _prompts:
        from app.services.rag.prompts import (
            APIDocTemplate,
            BaseDocTemplate,
            DocTemplateFactory,
            ModuleDocTemplate,
            ReadmeDocTemplate,
            generate_document,
        )
        mapping = {
            "APIDocTemplate": APIDocTemplate,
            "BaseDocTemplate": BaseDocTemplate,
            "DocTemplateFactory": DocTemplateFactory,
            "ModuleDocTemplate": ModuleDocTemplate,
            "ReadmeDocTemplate": ReadmeDocTemplate,
            "generate_document": generate_document,
        }
        return mapping[name]

    raise AttributeError(f"module 'app.services.rag' has no attribute {name!r}")


__all__ = [
    # 文档模板
    "APIDocTemplate",
    # 切分器
    "ASTChunkStrategy",
    "BaseChunkStrategy",
    "BaseDocTemplate",
    "ChunkStrategyFactory",
    # 数据模型
    "ChunkType",
    "CodeChunkMetadata",
    "CodeSplitter",
    "DocGenerateRequest",
    "DocGenerateResult",
    "DocTemplateFactory",
    "DocType",
    # Embedding
    "EmbeddingService",
    "FixedLengthChunkStrategy",
    "IndexRequest",
    "IndexResult",
    "LangChainEmbeddingAdapter",
    "MockEmbeddingService",
    "ModuleDocTemplate",
    "QAAnswer",
    "QAQuestion",
    # 问答链
    "RAGChain",
    "ReadmeDocTemplate",
    "RetrievedChunk",
    "SemanticChunkStrategy",
    "SimpleRAGService",
    "VectorRecord",
    # 向量存储
    "VectorStoreService",
    "generate_document",
    "get_embedding_service",
    "get_langchain_vector_store",
]
