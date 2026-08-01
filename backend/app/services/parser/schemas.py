"""解析管线数据模型。"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class SymbolType(str, Enum):
    """符号类型。"""

    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"
    INTERFACE = "interface"
    STRUCT = "struct"
    TRAIT = "trait"
    IMPL = "impl"
    ENUM = "enum"
    MODULE = "module"
    UNKNOWN = "unknown"


class CodeChunk(BaseModel):
    """一个 AST 切分得到的代码块。"""

    symbol_name: str = Field(..., description="符号名")
    symbol_type: SymbolType
    qualified_name: str = Field(..., description="带路径的全限定名，如 module.Class.method")
    file_path: str
    language: str
    start_line: int
    end_line: int
    start_byte: int
    end_byte: int
    content: str = Field(..., description="代码块原始文本")
    docstring: str | None = Field(default=None, description="紧邻的文档字符串/注释")

    @property
    def line_count(self) -> int:
        return self.end_line - self.start_line + 1


class FileInfo(BaseModel):
    """单文件解析结果。"""

    path: str
    language: str
    size_bytes: int
    total_lines: int
    symbol_count: int
    chunks: list[CodeChunk] = Field(default_factory=list)
    skipped: bool = False
    skip_reason: str | None = None


class ParsingResultSummary(BaseModel):
    """解析管线结果摘要（API 返回用）。"""

    repo_url: str
    total_files: int = 0
    parsed_files: int = 0
    skipped_files: int = 0
    total_symbols: int = 0
    total_chunks: int = 0
    files: list[FileInfo] = Field(default_factory=list)
    sample_chunks: list[CodeChunk] = Field(default_factory=list, description="前 N 个代码块样例")
    elapsed_seconds: float = 0.0
