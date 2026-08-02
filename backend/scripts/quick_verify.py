"""快速验证脚本：测试核心代码解析功能（不依赖外部服务）。"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path


def test_parsing_pipeline() -> bool:
    """测试代码解析管线。"""
    print("\n[1/4] 测试代码解析管线...")
    with tempfile.TemporaryDirectory() as tmp:
        sample = Path(tmp) / "sample.py"
        sample.write_text(
            '"""Demo 模块。"""\n'
            "from typing import List\n\n"
            "def process_data(items: List[str]) -> dict:\n"
            '    """处理数据。"""\n'
            "    result = {}\n"
            "    for item in items:\n"
            "        result[item] = item.upper()\n"
            "    return result\n\n"
            "class DataProcessor:\n"
            '    """数据处理器。"""\n'
            "    def __init__(self, name: str):\n"
            "        self.name = name\n"
            "        self.cache = {}\n\n"
            "    def run(self, items: List[str]) -> dict:\n"
            '        """运行处理。"""\n'
            "        return process_data(items)\n\n"
            "    def clear_cache(self):\n"
            '        """清除缓存。"""\n'
            "        self.cache.clear()\n",
            encoding="utf-8",
        )

        from app.services.parser.pipeline import ParsingPipeline
        pipeline = ParsingPipeline()
        summary = pipeline.run(tmp, repo_url="local://demo", max_files=50)

        assert summary.parsed_files >= 1
        assert summary.total_symbols >= 3
        sym_types = {c.symbol_type.value for c in summary.sample_chunks}
        print(f"  ✓ 文件={summary.parsed_files} 符号={summary.total_symbols} 代码块={summary.total_chunks}")
        print(f"  ✓ 符号类型={sym_types} 耗时={summary.elapsed_seconds:.3f}s")
    return True


def test_ast_splitter() -> bool:
    """测试 AST 切分器。"""
    print("\n[2/4] 测试 AST 切分器...")
    from app.services.rag.ast_splitter import ASTChunkStrategy

    strategy = ASTChunkStrategy()
    chunks = strategy.split(
        'def hello(name: str) -> str:\n    """打招呼。"""\n    return f"hi {name}"\n',
        file_path="/demo/test.py",
        language="python",
    )
    assert len(chunks) >= 1
    print(f"  ✓ 生成 {len(chunks)} 个代码块")
    for i, (content, meta) in enumerate(chunks):
        print(f"    [{i}] 符号={meta.get('symbol_name', '?')} 类型={meta.get('symbol_type', '?')}")
    return True


def test_call_graph() -> bool:
    """测试调用图分析。"""
    print("\n[3/4] 测试调用图分析...")
    from app.services.analyzer.call_graph import CallGraphExtractor
    from app.services.parser.schemas import CodeChunk

    extractor = CallGraphExtractor()

    chunks = [
        CodeChunk(
            symbol_name="process_data",
            qualified_name="demo.process_data",
            symbol_type="function",
            file_path="/demo/main.py",
            language="python",
            start_line=5, end_line=10,
            start_byte=0, end_byte=200,
            content="def process_data(items): ...",
        ),
        CodeChunk(
            symbol_name="run",
            qualified_name="demo.DataProcessor.run",
            symbol_type="method",
            file_path="/demo/main.py",
            language="python",
            start_line=20, end_line=22,
            start_byte=300, end_byte=400,
            content="def run(self, items): return process_data(items)",
        ),
    ]

    graph = extractor.extract(chunks)
    print(f"  ✓ 节点={len(graph.nodes)} 边={len(graph.edges)}")
    for node in graph.nodes:
        print(f"    节点: {node.id} ({node.type})")
    for edge in graph.edges:
        print(f"    边: {edge.source} -> {edge.target} ({edge.type})")
    return True


def test_prompt_templates() -> bool:
    """测试文档生成模板。"""
    print("\n[4/4] 测试文档生成模板...")
    from app.services.rag.prompts import ReadmeDocTemplate, APIDocTemplate, ModuleDocTemplate

    readme = ReadmeDocTemplate()
    result = readme.render(
        project_name="TestProject",
        project_description="A test project for CodeNova",
    )
    assert "TestProject" in result
    print(f"  ✓ README 模板渲染成功（{len(result)} 字符）")

    api = APIDocTemplate()
    result = api.render(
        module_name="api",
        functions=["func_a", "func_b"],
    )
    assert "api" in result
    print(f"  ✓ API 文档模板渲染成功（{len(result)} 字符）")

    module = ModuleDocTemplate()
    result = module.render(
        module_name="core",
        classes=["ClassA", "ClassB"],
    )
    assert "core" in result
    print(f"  ✓ 模块文档模板渲染成功（{len(result)} 字符）")
    return True


def main() -> int:
    print("=" * 50)
    print("CodeNova 核心功能快速验证")
    print("=" * 50)

    tests = [
        test_parsing_pipeline,
        test_ast_splitter,
        test_call_graph,
        test_prompt_templates,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'=' * 50}")
    print(f"结果: {passed}/{len(tests)} 通过, {failed} 失败")
    print(f"{'=' * 50}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
