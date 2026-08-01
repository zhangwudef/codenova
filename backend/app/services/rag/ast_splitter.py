"""AST 代码切分器。

提供多种切分策略：
- AST 切分：基于抽象语法树按函数/类/方法粒度切分
- 语义切分：基于代码语义结构进行切分
- 固定长度切分：按固定 token/字符长度切分

所有切分策略确保代码片段的语义完整性与独立性。
"""

from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod
from typing import ClassVar

from loguru import logger

from app.services.parser.schemas import CodeChunk, SymbolType
from app.services.parser.tree_sitter_parser import ast_parser
from app.services.rag.schemas import ChunkType, CodeChunkMetadata


class BaseChunkStrategy(ABC):
    """代码切分策略基类。"""

    @abstractmethod
    def split(self, source: str, file_path: str, language: str) -> list[tuple[str, CodeChunkMetadata]]:
        """切分源码，返回 (chunk_content, metadata) 列表。"""
        ...

    @staticmethod
    def _generate_chunk_id(content: str, file_path: str, index: int) -> str:
        """生成唯一的 chunk 标识。"""
        hash_input = f"{file_path}:{index}:{content[:100]}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]


class ASTChunkStrategy(BaseChunkStrategy):
    """基于 AST 的代码切分策略。

    利用已有的 Tree-sitter 解析器，将源代码按照逻辑结构
    （类、函数、方法、代码块等）进行智能分割。
    """

    def split(self, source: str, file_path: str, language: str) -> list[tuple[str, CodeChunkMetadata]]:
        """使用 AST 解析器进行代码切分。"""
        if not source or not source.strip():
            return []

        chunks = ast_parser.parse(source, file_path, language)

        if not chunks:
            logger.debug(f"AST 解析未产出代码块，回退至固定长度切分: {file_path}")
            return FixedLengthChunkStrategy().split(source, file_path, language)

        results: list[tuple[str, CodeChunkMetadata]] = []
        for chunk in chunks:
            metadata = self._build_metadata(chunk, file_path, language)
            results.append((chunk.content, metadata))

        logger.info(f"AST 切分完成: {file_path} -> {len(results)} 个代码块")
        return results

    def _build_metadata(self, chunk: CodeChunk, file_path: str, language: str) -> CodeChunkMetadata:
        """从 CodeChunk 构建元数据。"""
        chunk_type_map = {
            SymbolType.FUNCTION: ChunkType.FUNCTION,
            SymbolType.METHOD: ChunkType.METHOD,
            SymbolType.CLASS: ChunkType.CLASS,
            SymbolType.INTERFACE: ChunkType.INTERFACE,
            SymbolType.STRUCT: ChunkType.STRUCT,
            SymbolType.TRAIT: ChunkType.CLASS,
            SymbolType.IMPL: ChunkType.CLASS,
            SymbolType.ENUM: ChunkType.CLASS,
            SymbolType.MODULE: ChunkType.MODULE,
            SymbolType.UNKNOWN: ChunkType.PLAIN_TEXT,
        }

        chunk_type = chunk_type_map.get(chunk.symbol_type, ChunkType.FUNCTION)

        return CodeChunkMetadata(
            file_path=file_path,
            language=language,
            chunk_type=chunk_type,
            symbol_name=chunk.symbol_name,
            qualified_name=chunk.qualified_name,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            extra={
                "docstring": chunk.docstring or "",
                "line_count": chunk.line_count,
            },
        )


class SemanticChunkStrategy(BaseChunkStrategy):
    """基于语义的代码切分策略。

    当 AST 解析失败或返回空结果时，使用基于缩进和关键字的
    启发式方法进行语义切分。
    """

    KEYWORDS_PATTERNS: ClassVar[dict[str, list[re.Pattern[str]]]] = {
        "python": [
            re.compile(r"^(def |class |async def |@\w+)", re.MULTILINE),
        ],
        "javascript": [
            re.compile(r"^(function |const |let |class |export |import )", re.MULTILINE),
        ],
        "typescript": [
            re.compile(r"^(function |const |let |class |interface |export |import )", re.MULTILINE),
        ],
        "java": [
            re.compile(r"^(public |private |protected |class |interface |enum )", re.MULTILINE),
        ],
        "go": [
            re.compile(r"^(func |type |const |var |package )", re.MULTILINE),
        ],
        "rust": [
            re.compile(r"^(fn |struct |enum |trait |impl |pub |mod )", re.MULTILINE),
        ],
    }

    def split(self, source: str, file_path: str, language: str) -> list[tuple[str, CodeChunkMetadata]]:
        """基于语义模式切分。"""
        patterns = self.KEYWORDS_PATTERNS.get(language, self.KEYWORDS_PATTERNS["python"])

        split_positions: list[int] = [0]
        for pattern in patterns:
            for match in pattern.finditer(source):
                pos = match.start()
                if pos > 0 and pos - split_positions[-1] > 50:
                    split_positions.append(pos)

        if len(split_positions) <= 1:
            logger.debug(f"语义切分仅找到一个切点，回退至固定长度切分: {file_path}")
            return FixedLengthChunkStrategy().split(source, file_path, language)

        split_positions.append(len(source))
        results: list[tuple[str, CodeChunkMetadata]] = []

        for i in range(len(split_positions) - 1):
            start = split_positions[i]
            end = split_positions[i + 1]
            content = source[start:end].strip()

            if len(content) < 20:
                continue

            start_line = source[:start].count("\n") + 1
            end_line = source[:end].count("\n") + 1

            metadata = CodeChunkMetadata(
                file_path=file_path,
                language=language,
                chunk_type=ChunkType.FUNCTION,
                start_line=start_line,
                end_line=end_line,
                extra={"strategy": "semantic"},
            )
            results.append((content, metadata))

        logger.info(f"语义切分完成: {file_path} -> {len(results)} 个代码块")
        return results


class FixedLengthChunkStrategy(BaseChunkStrategy):
    """固定长度切分策略。

    按指定的最大 token 数或字符数进行切分，
    适用于无法进行 AST 或语义切分的场景。
    """

    def __init__(self, max_chars: int = 1500, overlap_chars: int = 200) -> None:
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars

    def split(self, source: str, file_path: str, language: str) -> list[tuple[str, CodeChunkMetadata]]:
        """按固定长度切分。"""
        if len(source) <= self.max_chars:
            metadata = CodeChunkMetadata(
                file_path=file_path,
                language=language,
                chunk_type=ChunkType.PLAIN_TEXT,
                start_line=1,
                end_line=source.count("\n") + 1,
                extra={"strategy": "fixed", "is_full_file": True},
            )
            return [(source, metadata)]

        chunks: list[tuple[str, CodeChunkMetadata]] = []
        start = 0
        source_len = len(source)
        max_iterations = (source_len // self.max_chars) * 3
        iterations = 0

        while start < source_len and iterations < max_iterations:
            iterations += 1
            end = min(start + self.max_chars, source_len)

            if end < source_len:
                boundary = self._find_safe_boundary(source, start, end)
                if boundary > start and boundary < source_len:
                    end = boundary

            content = source[start:end].strip()
            if content:
                start_line = source[:start].count("\n") + 1
                end_line = source[:end].count("\n") + 1

                metadata = CodeChunkMetadata(
                    file_path=file_path,
                    language=language,
                    chunk_type=ChunkType.PLAIN_TEXT,
                    start_line=start_line,
                    end_line=end_line,
                    extra={"strategy": "fixed", "char_offset": start},
                )
                chunks.append((content, metadata))

            next_start = end - self.overlap_chars
            if next_start <= start:
                start = end
            else:
                start = next_start

        logger.info(f"固定长度切分完成: {file_path} -> {len(chunks)} 个代码块")
        return chunks

    @staticmethod
    def _find_safe_boundary(source: str, start: int, end: int) -> int:
        """在指定范围内寻找安全的切分边界（如换行符）。"""
        search_start = max(start, end - 200)
        if search_start >= end:
            return end
        boundary = source.rfind("\n", search_start, end)
        if boundary == -1:
            boundary = source.rfind(";", search_start, end)
        if boundary == -1:
            boundary = source.rfind("}", search_start, end)
        return boundary if boundary > start else end


class ChunkStrategyFactory:
    """切分策略工厂。"""

    _strategies: ClassVar[dict[str, BaseChunkStrategy]] = {}

    @classmethod
    def get_strategy(cls, name: str) -> BaseChunkStrategy:
        """根据名称获取切分策略。"""
        if name not in cls._strategies:
            cls._strategies = {
                "ast": ASTChunkStrategy(),
                "semantic": SemanticChunkStrategy(),
                "fixed": FixedLengthChunkStrategy(),
            }
        strategy = cls._strategies.get(name)
        if strategy is None:
            raise ValueError(f"未知的切分策略: {name}")
        return strategy

    @classmethod
    def list_strategies(cls) -> list[str]:
        """列出所有可用的切分策略。"""
        return ["ast", "semantic", "fixed"]


class CodeSplitter:
    """代码切分器 - 对外统一接口。

    支持多种切分策略，并提供切分后的后处理功能，
    如过滤过短/过长片段、添加标识符等。
    """

    def __init__(self, strategy_name: str = "ast", min_chunk_chars: int = 50, max_chunk_chars: int = 4000) -> None:
        self.strategy = ChunkStrategyFactory.get_strategy(strategy_name)
        self.min_chunk_chars = min_chunk_chars
        self.max_chunk_chars = max_chunk_chars

    def split_file(self, source: str, file_path: str, language: str) -> list[tuple[str, CodeChunkMetadata]]:
        """切分单个文件。"""
        raw_chunks = self.strategy.split(source, file_path, language)
        filtered = self._post_process(raw_chunks, file_path)
        return filtered

    def split_batch(
        self, files: list[tuple[str, str, str]]
    ) -> list[tuple[str, CodeChunkMetadata]]:
        """批量切分多个文件。

        Args:
            files: [(source, file_path, language), ...]

        Returns:
            所有代码块列表
        """
        all_chunks: list[tuple[str, CodeChunkMetadata]] = []
        for source, file_path, language in files:
            chunks = self.split_file(source, file_path, language)
            all_chunks.extend(chunks)
        logger.info(f"批量切分完成: {len(files)} 文件 -> {len(all_chunks)} 代码块")
        return all_chunks

    def _post_process(
        self, chunks: list[tuple[str, CodeChunkMetadata]], file_path: str
    ) -> list[tuple[str, CodeChunkMetadata]]:
        """后处理：过滤、截断、添加ID。"""
        processed: list[tuple[str, CodeChunkMetadata]] = []

        for idx, (content, metadata) in enumerate(chunks):
            content_len = len(content)

            if content_len < self.min_chunk_chars:
                logger.debug(f"过滤过短代码块: {file_path} chunk#{idx} ({content_len} chars)")
                continue

            if content_len > self.max_chunk_chars:
                content = content[:self.max_chunk_chars] + "\n# ... (truncated)"
                logger.debug(f"截断过长代码块: {file_path} chunk#{idx}")

            metadata.extra["chunk_index"] = idx
            metadata.extra["char_length"] = len(content)

            processed.append((content, metadata))

        return processed
