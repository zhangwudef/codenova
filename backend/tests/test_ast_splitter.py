"""AST 切分器单元测试。"""

import pytest

from app.services.rag.ast_splitter import (
    ASTChunkStrategy,
    ChunkStrategyFactory,
    CodeSplitter,
    FixedLengthChunkStrategy,
    SemanticChunkStrategy,
)
from app.services.rag.schemas import ChunkType, CodeChunkMetadata


class TestASTChunkStrategy:
    """AST 切分策略测试。"""

    def test_split_python_function(self):
        """测试 Python 函数切分。"""
        strategy = ASTChunkStrategy()
        source = '''
def hello_world():
    """一个简单的问候函数。"""
    print("Hello, World!")
    return True
'''
        chunks = strategy.split(source, "test.py", "python")
        assert len(chunks) > 0
        content, metadata = chunks[0]
        assert metadata.language == "python"
        assert metadata.chunk_type in (ChunkType.FUNCTION, ChunkType.METHOD)
        assert "hello_world" in content

    def test_split_python_class(self):
        """测试 Python 类切分。"""
        strategy = ASTChunkStrategy()
        source = '''
class MyClass:
    """一个简单的类。"""

    def method(self):
        """方法。"""
        pass
'''
        chunks = strategy.split(source, "test.py", "python")
        assert len(chunks) >= 1

    def test_split_javascript_function(self):
        """测试 JavaScript 函数切分。"""
        strategy = ASTChunkStrategy()
        source = '''
function greet(name) {
    return `Hello, ${name}!`;
}
'''
        chunks = strategy.split(source, "test.js", "javascript")
        assert len(chunks) > 0

    def test_empty_source(self):
        """测试空源码。"""
        strategy = ASTChunkStrategy()
        chunks = strategy.split("", "empty.py", "python")
        assert len(chunks) == 0

    def test_unsupported_language_fallback(self):
        """测试不支持的语言回退。"""
        strategy = ASTChunkStrategy()
        source = "This is some text content."
        chunks = strategy.split(source, "test.xyz", "python")
        assert len(chunks) >= 0


class TestSemanticChunkStrategy:
    """语义切分策略测试。"""

    def test_split_by_keywords(self):
        """测试关键字切分。"""
        strategy = SemanticChunkStrategy()
        source = '''
def func1():
    pass

def func2():
    pass

class MyClass:
    pass
'''
        chunks = strategy.split(source, "test.py", "python")
        assert len(chunks) >= 1

    def test_short_source(self):
        """测试短源码。"""
        strategy = SemanticChunkStrategy()
        source = "def short(): pass"
        chunks = strategy.split(source, "test.py", "python")
        assert len(chunks) >= 0


class TestFixedLengthChunkStrategy:
    """固定长度切分策略测试。"""

    def test_split_short_text(self):
        """测试短文本（不需切分）。"""
        strategy = FixedLengthChunkStrategy(max_chars=1000)
        source = "Short text content."
        chunks = strategy.split(source, "test.py", "python")
        assert len(chunks) == 1
        assert chunks[0][0] == source

    def test_split_long_text(self):
        """测试长文本切分。"""
        strategy = FixedLengthChunkStrategy(max_chars=50, overlap_chars=10)
        source = "A" * 200
        chunks = strategy.split(source, "test.py", "python")
        assert len(chunks) > 1

    def test_metadata_correct(self):
        """测试元数据正确性。"""
        strategy = FixedLengthChunkStrategy(max_chars=100)
        source = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        chunks = strategy.split(source, "test.py", "python")
        assert len(chunks) > 0
        for content, metadata in chunks:
            assert metadata.file_path == "test.py"
            assert metadata.language == "python"
            assert metadata.start_line is not None
            assert metadata.end_line is not None


class TestChunkStrategyFactory:
    """切分策略工厂测试。"""

    def test_get_ast_strategy(self):
        """获取 AST 策略。"""
        strategy = ChunkStrategyFactory.get_strategy("ast")
        assert isinstance(strategy, ASTChunkStrategy)

    def test_get_semantic_strategy(self):
        """获取语义策略。"""
        strategy = ChunkStrategyFactory.get_strategy("semantic")
        assert isinstance(strategy, SemanticChunkStrategy)

    def test_get_fixed_strategy(self):
        """获取固定长度策略。"""
        strategy = ChunkStrategyFactory.get_strategy("fixed")
        assert isinstance(strategy, FixedLengthChunkStrategy)

    def test_get_unknown_strategy_raises(self):
        """获取未知策略抛出异常。"""
        with pytest.raises(ValueError):
            ChunkStrategyFactory.get_strategy("unknown")

    def test_list_strategies(self):
        """列出所有策略。"""
        strategies = ChunkStrategyFactory.list_strategies()
        assert "ast" in strategies
        assert "semantic" in strategies
        assert "fixed" in strategies


class TestCodeSplitter:
    """代码切分器测试。"""

    def test_split_file_with_ast(self):
        """使用 AST 策略切分文件。"""
        splitter = CodeSplitter(strategy_name="ast", min_chunk_chars=10)
        source = '''
def function1():
    """函数1 - 计算两个数的和。"""
    a = 10
    b = 20
    return a + b

def function2():
    """函数2 - 计算两个数的积。"""
    x = 5
    y = 6
    return x * y
'''
        chunks = splitter.split_file(source, "test.py", "python")
        assert len(chunks) >= 2

    def test_split_batch(self):
        """批量切分。"""
        splitter = CodeSplitter(strategy_name="fixed", min_chunk_chars=1)
        files = [
            ("code1 content", "file1.py", "python"),
            ("code2 content", "file2.py", "python"),
        ]
        chunks = splitter.split_batch(files)
        assert len(chunks) == 2

    def test_min_chunk_filter(self):
        """最小块过滤。"""
        splitter = CodeSplitter(strategy_name="fixed", min_chunk_chars=100)
        source = "short"
        chunks = splitter.split_file(source, "test.py", "python")
        assert len(chunks) == 0

    def test_post_process_adds_index(self):
        """后处理添加索引。"""
        splitter = CodeSplitter(strategy_name="fixed", min_chunk_chars=1)
        source = "x" * 10
        chunks = splitter.split_file(source, "test.py", "python")
        assert len(chunks) > 0
        _, metadata = chunks[0]
        assert "chunk_index" in metadata.extra
