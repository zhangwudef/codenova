"""Tree-sitter AST 解析器。

职责：
- 解析单文件源码为 AST
- 遍历 AST，按函数/类/方法粒度切分代码块（AST 级语义切分）
- 提取符号名、全限定名、行范围、文档字符串
"""

from __future__ import annotations

from loguru import logger

from app.services.parser.languages import LanguageRegistry
from app.services.parser.schemas import CodeChunk, SymbolType


class ASTParser:
    """基于 Tree-sitter 的单文件 AST 解析器。"""

    def parse(self, source: str, file_path: str, language: str) -> list[CodeChunk]:
        """解析源码，返回符号级代码块列表。

        Args:
            source: 源码文本
            file_path: 文件相对路径（用于元数据）
            language: 语言名（python/javascript/...）

        Returns:
            按 start_line 升序的代码块列表；解析失败返回空列表。
        """
        node_types = LanguageRegistry.symbol_node_types(language)
        if not node_types:
            return []

        try:
            parser = LanguageRegistry.get_parser(language)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"获取 {language} 解析器失败: {e}")
            return []

        source_bytes = source.encode("utf-8", errors="replace")
        try:
            tree = parser.parse(source_bytes)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"解析 {file_path} ({language}) 失败: {e}")
            return []

        chunks: list[CodeChunk] = []
        # 递归遍历，维护命名栈以构造全限定名；in_class 标记当前是否处于类体内
        self._walk(
            node=tree.root_node,
            source_bytes=source_bytes,
            file_path=file_path,
            language=language,
            node_types=node_types,
            name_stack=[],
            in_class=False,
            chunks=chunks,
        )
        chunks.sort(key=lambda c: c.start_line)
        return chunks

    # ------------------------------------------------------------------
    # 内部：递归遍历
    # ------------------------------------------------------------------
    def _walk(
        self,
        node,
        source_bytes: bytes,
        file_path: str,
        language: str,
        node_types: dict[str, SymbolType],
        name_stack: list[str],
        in_class: bool,
        chunks: list[CodeChunk],
    ) -> None:
        symbol_type = node_types.get(node.type)
        if symbol_type is not None:
            # Python 不区分函数/方法语法，类体内的 function_definition 视为方法
            if node.type == "function_definition" and in_class:
                symbol_type = SymbolType.METHOD
            chunk = self._build_chunk(
                node=node,
                source_bytes=source_bytes,
                file_path=file_path,
                language=language,
                symbol_type=symbol_type,
                name_stack=name_stack,
            )
            if chunk is not None:
                chunks.append(chunk)
                # 进入符号体时压栈，使内部符号获得全限定名
                new_stack = name_stack + [chunk.symbol_name]
                # 类体的直接子符号 in_class=True；函数体内嵌套定义不算方法
                child_in_class = symbol_type == SymbolType.CLASS
                for child in node.children:
                    self._walk(
                        node=child,
                        source_bytes=source_bytes,
                        file_path=file_path,
                        language=language,
                        node_types=node_types,
                        name_stack=new_stack,
                        in_class=child_in_class,
                        chunks=chunks,
                    )
                return

        # 非符号节点：继续向下遍历
        for child in node.children:
            self._walk(
                node=child,
                source_bytes=source_bytes,
                file_path=file_path,
                language=language,
                node_types=node_types,
                name_stack=name_stack,
                in_class=in_class,
                chunks=chunks,
            )

    def _build_chunk(
        self,
        node,
        source_bytes: bytes,
        file_path: str,
        language: str,
        symbol_type: SymbolType,
        name_stack: list[str],
    ) -> CodeChunk | None:
        name = self._extract_name(node, source_bytes)
        if not name:
            return None

        start_byte = node.start_byte
        end_byte = node.end_byte
        content = source_bytes[start_byte:end_byte].decode("utf-8", errors="replace")
        qualified = ".".join(name_stack + [name]) if name_stack else name

        docstring = self._extract_docstring(node, source_bytes, language)

        return CodeChunk(
            symbol_name=name,
            symbol_type=symbol_type,
            qualified_name=qualified,
            file_path=file_path,
            language=language,
            start_line=node.start_point[0] + 1,  # tree-sitter 行号从 0 开始
            end_line=node.end_point[0] + 1,
            start_byte=start_byte,
            end_byte=end_byte,
            content=content,
            docstring=docstring,
        )

    @staticmethod
    def _extract_name(node, source_bytes: bytes) -> str | None:
        """提取符号名：优先取 'name' 字段，否则找 identifier 子节点。

        使用源码字节切片读取文本，兼容各版本 tree-sitter。
        """
        name_node = node.child_by_field_name("name")
        if name_node is not None:
            return source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace")
        # 回退1：遍历直接子节点寻找 identifier
        for child in node.children:
            if child.type in ("identifier", "type_identifier", "property_identifier"):
                return source_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
        # 回退2：部分语言的声明节点名字嵌套在 spec 子节点中
        # （如 Go 的 type_declaration → type_spec.name），向下取一层
        for child in node.children:
            spec_name = child.child_by_field_name("name")
            if spec_name is not None:
                return source_bytes[spec_name.start_byte:spec_name.end_byte].decode("utf-8", errors="replace")
        return None

    @staticmethod
    def _extract_docstring(node, source_bytes: bytes, language: str) -> str | None:
        """提取文档字符串。

        Python: 函数/类体的首条语句若为字符串字面量则视为 docstring。
        其他语言暂返回 None（阶段二增强：提取前置注释块）。
        """
        if language != "python":
            return None

        # 找到 'body' / 'block' 子节点
        body = node.child_by_field_name("body") or node.child_by_field_name("block")
        if body is None or len(body.children) == 0:
            return None

        first = body.children[0]
        # expression_statement → string
        if first.type == "expression_statement" and first.children:
            inner = first.children[0]
            if inner.type == "string":
                text = source_bytes[inner.start_byte:inner.end_byte].decode("utf-8", errors="replace")
                # 去除引号
                if text.startswith(('"""', "'''")):
                    return text[3:-3].strip()
                if text.startswith(('"', "'")):
                    return text[1:-1].strip()
                return text
        return None


ast_parser = ASTParser()
