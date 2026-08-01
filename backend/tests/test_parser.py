"""AST 解析器单元测试。

验证「解析结果的准确性和完整性」——不依赖外部服务，可直接运行：
    cd backend && python -m pytest tests/test_parser.py -v
"""

from __future__ import annotations

import pytest

from app.services.parser.languages import LanguageRegistry
from app.services.parser.schemas import SymbolType
from app.services.parser.tree_sitter_parser import ast_parser


# ---------- Python ----------
PYTHON_SOURCE = '''"""模块文档。"""
def add(a: int, b: int) -> int:
    """两数相加。"""
    return a + b


class Calculator:
    """简单计算器。"""

    def multiply(self, x, y):
        return x * y

    def _private(self):
        pass
'''


def test_python_parses_functions_and_classes():
    chunks = ast_parser.parse(PYTHON_SOURCE, "calc.py", "python")
    names = {(c.symbol_name, c.symbol_type) for c in chunks}
    assert ("add", SymbolType.FUNCTION) in names
    assert ("Calculator", SymbolType.CLASS) in names
    assert ("multiply", SymbolType.METHOD) in names
    assert len(chunks) == 4  # add + Calculator + multiply + _private


def test_python_docstring_extraction():
    chunks = ast_parser.parse(PYTHON_SOURCE, "calc.py", "python")
    add_chunk = next(c for c in chunks if c.symbol_name == "add")
    assert add_chunk.docstring == "两数相加。"
    calc_chunk = next(c for c in chunks if c.symbol_name == "Calculator")
    assert calc_chunk.docstring == "简单计算器。"


def test_python_qualified_name():
    chunks = ast_parser.parse(PYTHON_SOURCE, "calc.py", "python")
    multiply = next(c for c in chunks if c.symbol_name == "multiply")
    assert multiply.qualified_name == "Calculator.multiply"


def test_python_line_range():
    chunks = ast_parser.parse(PYTHON_SOURCE, "calc.py", "python")
    add_chunk = next(c for c in chunks if c.symbol_name == "add")
    assert add_chunk.start_line == 2
    assert add_chunk.end_line == 4


# ---------- JavaScript ----------
JS_SOURCE = """
function greet(name) {
  return `Hello, ${name}`;
}

class Greeter {
  sayHi() {
    return greet('world');
  }
}
"""


def test_javascript_parsing():
    chunks = ast_parser.parse(JS_SOURCE, "greet.js", "javascript")
    names = {c.symbol_name for c in chunks}
    assert "greet" in names
    assert "Greeter" in names
    assert "sayHi" in names


# ---------- Go ----------
GO_SOURCE = """
package main

func add(a int, b int) int {
    return a + b
}

type Calculator struct {
    base int
}
"""


def test_go_parsing():
    chunks = ast_parser.parse(GO_SOURCE, "calc.go", "go")
    names = {c.symbol_name for c in chunks}
    assert "add" in names
    assert "Calculator" in names


# ---------- 语言检测 ----------
def test_language_detection():
    assert LanguageRegistry.detect_language("foo.py") == "python"
    assert LanguageRegistry.detect_language("bar.ts") == "typescript"
    assert LanguageRegistry.detect_language("baz.go") == "go"
    assert LanguageRegistry.detect_language("readme.md") is None


def test_unknown_language_returns_empty():
    chunks = ast_parser.parse("hello", "x.txt", "python")
    assert chunks == []


def test_invalid_syntax_does_not_crash():
    # 语法错误的代码也应返回（可能为空或部分），不应抛异常
    chunks = ast_parser.parse("def (", "bad.py", "python")
    assert isinstance(chunks, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
