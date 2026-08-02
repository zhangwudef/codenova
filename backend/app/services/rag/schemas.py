"""RAG 模块数据模型定义。

定义代码切分、向量存储、问答链等核心数据结构。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ChunkType(str, Enum):
    """代码块类型。"""

    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    INTERFACE = "interface"
    STRUCT = "struct"
    MODULE = "module"
    DOCUMENT = "document"
    PLAIN_TEXT = "plain_text"


class CodeChunkMetadata(BaseModel):
    """代码块元数据。"""

    file_path: str
    language: str
    chunk_type: ChunkType = ChunkType.FUNCTION
    symbol_name: str | None = None
    qualified_name: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    repo_url: str | None = None
    extra: dict = Field(default_factory=dict)


class VectorRecord(BaseModel):
    """向量存储记录。"""

    id: str
    content: str
    metadata: CodeChunkMetadata
    vector: list[float] | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class RetrievedChunk(BaseModel):
    """检索返回的代码块。"""

    content: str
    metadata: CodeChunkMetadata
    score: float = 0.0


class QAQuestion(BaseModel):
    """问答请求。"""

    question: str
    repo_url: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)
    score_threshold: float = Field(default=0.5, ge=0.0, le=1.0)


class QAAnswer(BaseModel):
    """问答响应。"""

    answer: str
    sources: list[RetrievedChunk] = Field(default_factory=list)
    question: str
    model: str | None = None
    latency_ms: float = 0.0


class IndexRequest(BaseModel):
    """索引构建请求。"""

    repo_url: str
    branch: str | None = None
    max_files: int = Field(default=200, ge=1, le=2000)
    chunk_strategy: str = Field(default="ast", description="切分策略: ast/semantic/fixed")


class IndexResult(BaseModel):
    """索引构建结果。"""

    repo_url: str
    total_files: int = 0
    total_chunks: int = 0
    total_embeddings: int = 0
    collection_name: str
    elapsed_seconds: float = 0.0


class DocType(str, Enum):
    """文档类型。"""

    README = "readme"
    API = "api"
    MODULE = "module"


class DocGenerateRequest(BaseModel):
    """文档生成请求。"""

    doc_type: DocType
    target_path: str | None = None
    module_name: str | None = None
    repo_url: str | None = None
    extra_context: dict = Field(default_factory=dict)


class DocGenerateResult(BaseModel):
    """文档生成结果。"""

    doc_type: DocType
    content: str
    template_used: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    # RAG 增强相关字段（文档 2.1 节）
    used_rag: bool = False
    repo_url: str | None = None
    rag_sources: list[RetrievedChunk] = Field(default_factory=list)


class QAPersistReference(BaseModel):
    """固化文档中的引用信息。"""

    file_path: str
    line_start: int | None = None
    line_end: int | None = None
    code: str | None = None


class QAPersistMessage(BaseModel):
    """固化文档中的单条问答消息。"""

    role: str = Field(..., description="user 或 assistant")
    content: str
    timestamp: float | None = None
    references: list[QAPersistReference] = Field(default_factory=list)


class QAPersistRequest(BaseModel):
    """问答固化请求（文档 4.2 节「问答即文档」）。"""

    title: str = Field(default="CodeNova 问答沉淀", description="文档标题")
    repo_url: str | None = None
    messages: list[QAPersistMessage] = Field(default_factory=list)
    # 仅固化 pinned 消息时为 True
    pinned_only: bool = Field(default=False)


class QAPersistResult(BaseModel):
    """问答固化结果。"""

    object_name: str
    bucket: str
    download_url: str | None = None
    content: str = Field(..., description="生成的 Markdown 全文，便于前端预览")
    message_count: int
    saved_at: datetime = Field(default_factory=datetime.utcnow)
