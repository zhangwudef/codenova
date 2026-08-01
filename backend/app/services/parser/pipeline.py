"""代码解析管线。

职责：遍历仓库目录 → 过滤文件 → AST 解析 → 聚合结果摘要。
这是阶段一的核心交付物，验证「代码解析管线能够稳定运行并输出预期结果」。
"""

from __future__ import annotations

import time
from pathlib import Path

from loguru import logger

from app.core.config import settings
from app.services.parser.languages import LanguageRegistry
from app.services.parser.schemas import (
    CodeChunk,
    FileInfo,
    ParsingResultSummary,
)
from app.services.parser.tree_sitter_parser import ast_parser


class ParsingPipeline:
    """端到端代码解析管线。"""

    def __init__(self) -> None:
        self.ignore_dirs = set(settings.ignore_dirs)
        self.ignore_extensions = tuple(settings.ignore_extensions)
        self.max_file_size = settings.max_file_size_kb * 1024

    def run(
        self,
        repo_path: Path | str,
        repo_url: str = "",
        max_files: int = 200,
    ) -> ParsingResultSummary:
        """解析整个仓库目录。

        Args:
            repo_path: 本地仓库根目录
            repo_url: 仓库地址（写入摘要，便于追溯）
            max_files: 最多解析的文件数（防止超大仓库拖慢）

        Returns:
            解析结果摘要
        """
        start = time.perf_counter()
        repo_path = Path(repo_path)

        files_info: list[FileInfo] = []
        all_chunks: list[CodeChunk] = []
        scanned = 0

        for file_path in self._iter_source_files(repo_path):
            if scanned >= max_files:
                logger.info(f"达到 max_files={max_files} 上限，停止扫描")
                break
            scanned += 1

            info = self._parse_file(file_path, repo_path)
            files_info.append(info)
            all_chunks.extend(info.chunks)

        elapsed = time.perf_counter() - start
        parsed = sum(1 for f in files_info if not f.skipped)
        skipped = sum(1 for f in files_info if f.skipped)

        logger.info(
            f"管线完成: 扫描={scanned} 解析={parsed} 跳过={skipped} "
            f"符号={len(all_chunks)} 耗时={elapsed:.2f}s"
        )

        return ParsingResultSummary(
            repo_url=repo_url,
            total_files=scanned,
            parsed_files=parsed,
            skipped_files=skipped,
            total_symbols=len(all_chunks),
            total_chunks=len(all_chunks),
            files=files_info,
            sample_chunks=all_chunks[:5],
            elapsed_seconds=elapsed,
        )

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    def _iter_source_files(self, root: Path):
        """遍历目录，跳过忽略目录与忽略扩展名。"""
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            # 跳过忽略目录下的文件
            try:
                rel_parts = path.relative_to(root).parts
            except ValueError:
                continue
            if any(part in self.ignore_dirs for part in rel_parts):
                continue
            # 跳过忽略扩展名（.min.js 等）
            name = path.name.lower()
            if name.endswith(self.ignore_extensions):
                continue
            # 仅处理受支持语言
            if LanguageRegistry.detect_language(str(path)) is None:
                continue
            yield path

    def _parse_file(self, file_path: Path, repo_root: Path) -> FileInfo:
        """解析单个文件。"""
        rel_path = str(file_path.relative_to(repo_root)).replace("\\", "/")
        language = LanguageRegistry.detect_language(str(file_path)) or "unknown"

        size = file_path.stat().st_size
        if size > self.max_file_size:
            logger.debug(f"跳过大文件 {rel_path} ({size} bytes)")
            return FileInfo(
                path=rel_path, language=language, size_bytes=size, total_lines=0,
                symbol_count=0, skipped=True, skip_reason="file_too_large",
            )

        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            logger.warning(f"读取失败 {rel_path}: {e}")
            return FileInfo(
                path=rel_path, language=language, size_bytes=size, total_lines=0,
                symbol_count=0, skipped=True, skip_reason="read_error",
            )

        total_lines = source.count("\n") + (1 if source and not source.endswith("\n") else 0)
        chunks = ast_parser.parse(source, rel_path, language)

        return FileInfo(
            path=rel_path,
            language=language,
            size_bytes=size,
            total_lines=total_lines,
            symbol_count=len(chunks),
            chunks=chunks,
        )
