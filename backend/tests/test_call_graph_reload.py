"""调用关系图提取器回归测试。

重点验证 call_graph.py 的源码重读修复：当传入 repo_path 时，应重新读取
原始文件做 AST 重解析，使 CodeChunk 字节偏移与源码一致，从而将 call 边
正确归属到包含它的函数节点（而非模块节点）。

运行：
    cd backend && python -m pytest tests/test_call_graph_reload.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.analyzer.call_graph import CallGraphExtractor
from app.services.analyzer.schemas import EdgeType, NodeType
from app.services.parser.languages import LanguageRegistry
from app.services.parser.pipeline import ParsingPipeline


# 构造要点：函数之间存在大量顶层代码（模块文档串、import、注释、模块级
# 赋值）。这些内容不属于任何 AST chunk，因此「拼接 chunks」得到的源码与
# 原始文件的字节偏移必然不一致——这正是 line-231 缺陷的触发条件。
SOURCE = '''"""Module docstring."""
import os
import sys

# ------------------------------------------------------------------
# 一段较长的顶层注释与模块级代码，位于符号之间，不会被 AST 切分进任何
# chunk。它保证 chunk 的 start_byte/end_byte（相对原始文件）与拼接后
# 的源码偏移不匹配，从而触发重读缺陷。
# ------------------------------------------------------------------


CONSTANT = 42


def helper() -> int:
    """Return a constant."""
    return 42


def caller() -> int:
    """Call helper."""
    return helper()


def other_caller() -> int:
    """Call caller."""
    return caller()
'''


@pytest.fixture(scope="module", autouse=True)
def _ensure_python_parser() -> None:
    """预热 Python tree-sitter 解析器。"""
    LanguageRegistry.get_parser("python")


def _build_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "mod.py").write_text(SOURCE, encoding="utf-8")
    return repo


def _function_call_sources(graph):
    """返回 source 为函数节点（非 module）的 call 边。"""
    node_by_id = {n.id: n for n in graph.nodes}
    call_edges = [e for e in graph.edges if e.type == EdgeType.CALL]
    return [
        e for e in call_edges
        if node_by_id[e.source].type == NodeType.FUNCTION
    ], call_edges


def test_extract_with_repo_path_attributes_calls_to_function(tmp_path: Path) -> None:
    """传入 repo_path：重读原始文件，call 边归属到包含函数节点。

    这是修复后的正确行为：caller -> helper 的 source 应为 caller 函数节点，
    而非模块节点。仅当字节偏移与原始源码一致时才能正确定位调用者。
    """
    repo = _build_repo(tmp_path)
    summary = ParsingPipeline().run(repo, repo_url="test", max_files=10)
    graph = CallGraphExtractor().extract(
        summary.files, repo_url="test", repo_path=repo
    )

    function_call_sources, call_edges = _function_call_sources(graph)
    assert call_edges, "应至少提取到一条 call 边"
    assert function_call_sources, (
        "传入 repo_path 时，call 边应归属到函数节点而非模块节点；"
        "若失败说明原始文件重读未生效"
    )

    # 验证具体调用关系：caller -> helper
    node_by_id = {n.id: n for n in graph.nodes}
    caller_to_helper = [
        e for e in function_call_sources
        if node_by_id[e.source].label == "caller"
        and node_by_id[e.target].label == "helper"
    ]
    assert caller_to_helper, "应存在 caller -> helper 的函数级 call 边"


def test_extract_without_repo_path_degrades_to_module(tmp_path: Path) -> None:
    """未传 repo_path：回退拼接 chunks，字节偏移不一致，call 边降级归属到模块。

    该用例记录修复前的降级行为，作为对照，证明 repo_path 修复的必要性。
    """
    repo = _build_repo(tmp_path)
    summary = ParsingPipeline().run(repo, repo_url="test", max_files=10)
    graph = CallGraphExtractor().extract(
        summary.files, repo_url="test", repo_path=None
    )

    function_call_sources, call_edges = _function_call_sources(graph)
    assert call_edges, "即使降级，call 边仍应被提取（target 按 symbol 名解析）"
    assert not function_call_sources, (
        "未传 repo_path 时，因字节偏移不匹配，call 边应降级到模块节点；"
        "若出现函数级归属，说明测试用例已无法触发偏移不一致条件"
    )
