"""Tree-sitter 多语言注册表（现代独立语言包 API）。

职责：
- 文件扩展名 → 语言映射
- 语言 → 符号节点类型映射（AST 中哪些节点代表可切分的符号）
- 提供 tree-sitter 解析器（基于各语言的独立包，兼容 Python 3.11–3.14）

采用 tree-sitter 0.26 + 各语言独立包（tree-sitter-python 等），
而非 tree-sitter-languages（后者仅支持 Python <3.12）。
"""

from __future__ import annotations

from functools import lru_cache

from loguru import logger
from tree_sitter import Language, Parser

from app.services.parser.schemas import SymbolType

# ---------- 扩展名 → 语言 ----------
_EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
}

# ---------- 语言 → 符号节点类型 → 符号类别 ----------
# AST 中出现这些节点类型即视为一个可切分符号
_SYMBOL_NODE_TYPES: dict[str, dict[str, SymbolType]] = {
    "python": {
        "function_definition": SymbolType.FUNCTION,
        "class_definition": SymbolType.CLASS,
    },
    "javascript": {
        "function_declaration": SymbolType.FUNCTION,
        "class_declaration": SymbolType.CLASS,
        "method_definition": SymbolType.METHOD,
        "generator_function_declaration": SymbolType.FUNCTION,
    },
    "typescript": {
        "function_declaration": SymbolType.FUNCTION,
        "class_declaration": SymbolType.CLASS,
        "method_definition": SymbolType.METHOD,
        "interface_declaration": SymbolType.INTERFACE,
        "enum_declaration": SymbolType.ENUM,
        "abstract_class_declaration": SymbolType.CLASS,
        "function_signature": SymbolType.FUNCTION,
    },
    "tsx": {
        "function_declaration": SymbolType.FUNCTION,
        "class_declaration": SymbolType.CLASS,
        "method_definition": SymbolType.METHOD,
        "interface_declaration": SymbolType.INTERFACE,
        "abstract_class_declaration": SymbolType.CLASS,
    },
    "java": {
        "method_declaration": SymbolType.METHOD,
        "class_declaration": SymbolType.CLASS,
        "interface_declaration": SymbolType.INTERFACE,
        "enum_declaration": SymbolType.ENUM,
        "constructor_declaration": SymbolType.METHOD,
    },
    "go": {
        "function_declaration": SymbolType.FUNCTION,
        "method_declaration": SymbolType.METHOD,
        "type_spec": SymbolType.STRUCT,
    },
    "rust": {
        "function_item": SymbolType.FUNCTION,
        "struct_item": SymbolType.STRUCT,
        "trait_item": SymbolType.TRAIT,
        "impl_item": SymbolType.IMPL,
        "enum_item": SymbolType.ENUM,
    },
}


# ---------- 语言包加载函数 ----------
def _load_language(name: str) -> Language:
    """从独立语言包构造 Language 对象。"""
    if name == "python":
        import tree_sitter_python as t

        return Language(t.language())
    if name == "javascript":
        import tree_sitter_javascript as t

        return Language(t.language())
    if name == "typescript":
        import tree_sitter_typescript as t

        return Language(t.language_typescript())
    if name == "tsx":
        import tree_sitter_typescript as t

        return Language(t.language_tsx())
    if name == "java":
        import tree_sitter_java as t

        return Language(t.language())
    if name == "go":
        import tree_sitter_go as t

        return Language(t.language())
    if name == "rust":
        import tree_sitter_rust as t

        return Language(t.language())
    raise ValueError(f"不支持的语言: {name}")


class LanguageRegistry:
    """语言注册表：管理扩展名、符号类型与解析器。"""

    SUPPORTED = tuple(_EXTENSION_MAP.keys())

    @staticmethod
    def detect_language(file_path: str) -> str | None:
        """根据扩展名检测语言，未知返回 None。"""
        from pathlib import Path

        ext = Path(file_path).suffix.lower()
        return _EXTENSION_MAP.get(ext)

    @staticmethod
    def symbol_node_types(language: str) -> dict[str, SymbolType]:
        return _SYMBOL_NODE_TYPES.get(language, {})

    @staticmethod
    @lru_cache(maxsize=16)
    def get_language(language: str) -> Language:
        """获取 tree-sitter Language 对象（懒加载并缓存）。"""
        return _load_language(language)

    @staticmethod
    @lru_cache(maxsize=16)
    def get_parser(language: str) -> Parser:
        """获取 tree-sitter 解析器（懒加载并缓存）。"""
        return Parser(LanguageRegistry.get_language(language))

    @staticmethod
    def build_all() -> None:
        """预热：预加载所有受支持语言的解析器，避免运行时首次解析延迟。"""
        seen_langs: set[str] = set()
        for lang in _EXTENSION_MAP.values():
            if lang in seen_langs:
                continue
            seen_langs.add(lang)
            try:
                LanguageRegistry.get_parser(lang)
                LanguageRegistry.get_language(lang)
                logger.debug(f"已预热语言解析器: {lang}")
            except Exception as e:  # noqa: BLE001
                logger.warning(f"预热语言 {lang} 失败: {e}")
        logger.info(f"Tree-sitter 语言预热完成: {sorted(seen_langs)}")
