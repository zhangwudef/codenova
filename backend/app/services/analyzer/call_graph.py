"""基于 Tree-sitter AST 的调用关系图提取器。

职责：
- 从已解析的 FileInfo 列表中构建节点（module/class/function/interface）
- 提取四类关系边：import / call / inherit / implement
- 提供调用链遍历能力，供时序图生成使用（文档 3.2 / 3.3 节）

设计说明：
- 节点直接复用 ASTParser 已切分的 CodeChunk，避免重复解析符号
- 边需重新遍历 AST（符号提取阶段未保留关系信息），按语言节点类型匹配
- 边目标解析采用「尽力匹配」策略：先按全限定名精确匹配，再按符号名匹配
"""

from __future__ import annotations

import time
from collections import defaultdict
from pathlib import Path

from loguru import logger

from app.services.analyzer.schemas import (
    EdgeType,
    GraphData,
    GraphEdge,
    GraphNode,
    NodeType,
    SequenceData,
    SequenceMessage,
    SequenceParticipant,
)
from app.services.parser.languages import LanguageRegistry
from app.services.parser.schemas import FileInfo, SymbolType


# 各语言「关系节点类型」映射
_RELATION_NODE_TYPES: dict[str, dict[str, tuple[str, ...]]] = {
    "python": {
        "import": ("import_statement", "import_from_statement"),
        "call": ("call",),
        "class": ("class_definition",),
    },
    "javascript": {
        "import": ("import_statement",),
        "call": ("call_expression",),
        "class": ("class_declaration",),
    },
    "typescript": {
        "import": ("import_statement",),
        "call": ("call_expression",),
        "class": ("class_declaration", "abstract_class_declaration"),
        "interface": ("interface_declaration",),
    },
    "tsx": {
        "import": ("import_statement",),
        "call": ("call_expression",),
        "class": ("class_declaration", "abstract_class_declaration"),
        "interface": ("interface_declaration",),
    },
    "java": {
        "import": ("import_declaration",),
        "call": ("method_invocation",),
        "class": ("class_declaration",),
        "interface": ("interface_declaration",),
    },
    "go": {
        "import": ("import_declaration",),
        "call": ("call_expression",),
        "class": (),  # Go 无类继承
    },
    "rust": {
        "import": ("use_declaration",),
        "call": ("call_expression", "macro_invocation"),
        "class": ("struct_item",),
    },
}

# SymbolType → NodeType 映射
_SYMBOL_TO_NODE: dict[SymbolType, NodeType] = {
    SymbolType.FUNCTION: NodeType.FUNCTION,
    SymbolType.METHOD: NodeType.FUNCTION,
    SymbolType.CLASS: NodeType.CLASS,
    SymbolType.INTERFACE: NodeType.INTERFACE,
    SymbolType.STRUCT: NodeType.CLASS,
    SymbolType.TRAIT: NodeType.INTERFACE,
    SymbolType.IMPL: NodeType.CLASS,
    SymbolType.ENUM: NodeType.CLASS,
    SymbolType.MODULE: NodeType.MODULE,
    SymbolType.UNKNOWN: NodeType.FUNCTION,
}


def _node_id(file_path: str, qualified_name: str, node_type: NodeType) -> str:
    """生成节点唯一 ID。"""
    return f"{node_type.value}:{file_path}:{qualified_name}"


def _module_id(file_path: str) -> str:
    return f"module:{file_path}"


class CallGraphExtractor:
    """调用关系图提取器。"""

    def extract(
        self,
        files_info: list[FileInfo],
        repo_url: str = "",
        repo_path: Path | str | None = None,
    ) -> GraphData:
        """从解析结果提取完整依赖图。

        Args:
            files_info: ParsingPipeline 输出的文件信息列表
            repo_url: 仓库地址（写入结果便于追溯）
            repo_path: 本地仓库根目录。提供时会重新读取原始文件做 AST
                重解析，使 CodeChunk 的字节偏移与源码一致，边归属准确；
                为 None 时回退到拼接 chunks（偏移不保证准确，边归属降级）。

        Returns:
            GraphData: 节点+边列表
        """
        start = time.perf_counter()

        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []
        edge_seen: set[tuple[str, str, str]] = set()  # 去重

        # ---------- 第一遍：构建节点 + 索引 ----------
        # symbol_by_name: 符号名 -> [node_id]（同名符号可能存在多个）
        symbol_by_name: dict[str, list[str]] = defaultdict(list)
        # qualified_by_suffix: 全限定名末尾段 -> [node_id]（用于宽松匹配）
        qualified_by_suffix: dict[str, list[str]] = defaultdict(list)
        # module_by_path: 文件路径 -> module_node_id
        module_by_path: dict[str, str] = {}
        # module_by_basename: 文件 basename（去扩展名）-> [module_node_id]
        module_by_basename: dict[str, list[str]] = defaultdict(list)
        # node_by_id: node_id -> GraphNode（用于边目标补全）
        node_by_id: dict[str, GraphNode] = {}

        for file_info in files_info:
            if file_info.skipped or not file_info.chunks:
                # 仍为空文件创建模块节点
                if not file_info.skipped:
                    mid = _module_id(file_info.path)
                    module_by_path[file_info.path] = mid
                    module_by_basename[Path(file_info.path).stem].append(mid)
                    node = GraphNode(
                        id=mid, type=NodeType.MODULE,
                        label=Path(file_info.path).name, file_path=file_info.path,
                        qualified_name=file_info.path,
                    )
                    nodes.append(node)
                    node_by_id[mid] = node
                continue

            # 模块节点
            mid = _module_id(file_info.path)
            module_by_path[file_info.path] = mid
            module_by_basename[Path(file_info.path).stem].append(mid)
            module_node = GraphNode(
                id=mid, type=NodeType.MODULE,
                label=Path(file_info.path).name, file_path=file_info.path,
                qualified_name=file_info.path,
            )
            nodes.append(module_node)
            node_by_id[mid] = module_node

            # 符号节点
            for chunk in file_info.chunks:
                node_type = _SYMBOL_TO_NODE.get(chunk.symbol_type, NodeType.FUNCTION)
                nid = _node_id(file_info.path, chunk.qualified_name, node_type)
                node = GraphNode(
                    id=nid, type=node_type, label=chunk.symbol_name,
                    file_path=file_info.path, qualified_name=chunk.qualified_name,
                    start_line=chunk.start_line, end_line=chunk.end_line,
                )
                nodes.append(node)
                node_by_id[nid] = node
                symbol_by_name[chunk.symbol_name].append(nid)
                # 全限定名末尾段（如 module.Class.method -> Class.method / method）
                parts = chunk.qualified_name.split(".")
                for i in range(len(parts)):
                    qualified_by_suffix[".".join(parts[i:])].append(nid)

        # ---------- 第二遍：提取边 ----------
        for file_info in files_info:
            if file_info.skipped:
                continue
            try:
                self._extract_edges(
                    file_info=file_info,
                    module_id=module_by_path.get(file_info.path, _module_id(file_info.path)),
                    symbol_by_name=symbol_by_name,
                    qualified_by_suffix=qualified_by_suffix,
                    module_by_basename=module_by_basename,
                    edges=edges,
                    edge_seen=edge_seen,
                    repo_path=repo_path,
                )
            except Exception as e:  # noqa: BLE001
                logger.warning(f"提取关系边失败 {file_info.path}: {e}")

        elapsed = time.perf_counter() - start
        logger.info(
            f"依赖图构建完成: 节点={len(nodes)} 边={len(edges)} 耗时={elapsed:.3f}s"
        )
        return GraphData(
            nodes=nodes, edges=edges, repo_url=repo_url, elapsed_seconds=elapsed
        )

    # ------------------------------------------------------------------
    # 边提取
    # ------------------------------------------------------------------
    def _extract_edges(
        self,
        file_info: FileInfo,
        module_id: str,
        symbol_by_name: dict[str, list[str]],
        qualified_by_suffix: dict[str, list[str]],
        module_by_basename: dict[str, list[str]],
        edges: list[GraphEdge],
        edge_seen: set[tuple[str, str, str]],
        repo_path: Path | str | None = None,
    ) -> None:
        """重新解析单文件 AST，提取四类关系边。"""
        language = file_info.language
        rel_types = _RELATION_NODE_TYPES.get(language)
        if not rel_types:
            return

        try:
            parser = LanguageRegistry.get_parser(language)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"获取 {language} 解析器失败: {e}")
            return

        # 重新读取源码用于 AST 重解析。优先从 repo_path 读取原始文件：
        # 此时 CodeChunk 的 start_byte/end_byte 与源码一致，_find_containing_symbol
        # 能准确定位调用者；无 repo_path 时回退到拼接 chunks（偏移不保证准确）。
        source, is_original = self._load_source(file_info, repo_path)
        if not source.strip():
            return
        if not is_original:
            logger.debug(
                f"未提供 repo_path 或读取失败，回退拼接 chunks: {file_info.path} "
                "（call 边归属可能不准）"
            )

        source_bytes = source.encode("utf-8", errors="replace")
        try:
            tree = parser.parse(source_bytes)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"重解析 {file_info.path} 失败: {e}")
            return

        # 收集本文件的符号节点 ID（按字节范围索引，用于定位调用者）
        local_symbols: list[tuple[int, int, str, NodeType]] = []  # (start_byte, end_byte, node_id, type)
        for c in file_info.chunks:
            node_type = _SYMBOL_TO_NODE.get(c.symbol_type, NodeType.FUNCTION)
            nid = _node_id(file_info.path, c.qualified_name, node_type)
            local_symbols.append((c.start_byte, c.end_byte, nid, node_type))

        # 遍历 AST 提取边
        self._walk_for_edges(
            node=tree.root_node,
            source_bytes=source_bytes,
            language=language,
            rel_types=rel_types,
            module_id=module_id,
            local_symbols=local_symbols,
            symbol_by_name=symbol_by_name,
            qualified_by_suffix=qualified_by_suffix,
            module_by_basename=module_by_basename,
            edges=edges,
            edge_seen=edge_seen,
        )

    @staticmethod
    def _load_source(file_info: FileInfo, repo_path: Path | str | None) -> tuple[str, bool]:
        """加载文件源码用于 AST 重解析。

        优先从 repo_path 重新读取原始文件：此时源码与 CodeChunk 的
        start_byte/end_byte 一致，``_find_containing_symbol`` 能准确定位
        调用者，call 边归属正确。
        当 repo_path 为空或读取失败时，回退到拼接 chunks（偏移不保证准确，
        边归属降级），保留向后兼容与无仓库路径场景（如单元测试）的可用性。

        Returns:
            (source_text, is_original): 源码字符串 + 是否为原始文件
        """
        if repo_path:
            try:
                full_path = Path(repo_path) / file_info.path
                if full_path.is_file():
                    return full_path.read_text(encoding="utf-8", errors="replace"), True
            except OSError as e:
                logger.debug(f"重读源文件失败 {file_info.path}: {e}")
        # 回退：拼接 chunks（偏移不保证准确，仅保证不阻断流程）
        return "\n".join(c.content for c in file_info.chunks), False

    def _walk_for_edges(
        self,
        node,
        source_bytes: bytes,
        language: str,
        rel_types: dict[str, tuple[str, ...]],
        module_id: str,
        local_symbols: list[tuple[int, int, str, NodeType]],
        symbol_by_name: dict[str, list[str]],
        qualified_by_suffix: dict[str, list[str]],
        module_by_basename: dict[str, list[str]],
        edges: list[GraphEdge],
        edge_seen: set[tuple[str, str, str]],
    ) -> None:
        """递归遍历 AST，按节点类型提取关系边。"""
        node_type = node.type

        # 1) import 边
        if node_type in rel_types.get("import", ()):
            self._add_import_edge(
                node=node, source_bytes=source_bytes, language=language,
                module_id=module_id, module_by_basename=module_by_basename,
                edges=edges, edge_seen=edge_seen,
            )

        # 2) call 边
        if node_type in rel_types.get("call", ()):
            caller_id = self._find_containing_symbol(node.start_byte, local_symbols) or module_id
            self._add_call_edge(
                node=node, source_bytes=source_bytes, language=language,
                caller_id=caller_id, symbol_by_name=symbol_by_name,
                qualified_by_suffix=qualified_by_suffix,
                edges=edges, edge_seen=edge_seen,
            )

        # 3) inherit / implement 边
        if node_type in rel_types.get("class", ()):
            self._add_inherit_edges(
                node=node, source_bytes=source_bytes, language=language,
                file_module_id=module_id, symbol_by_name=symbol_by_name,
                qualified_by_suffix=qualified_by_suffix,
                edges=edges, edge_seen=edge_seen,
            )

        if node_type in rel_types.get("interface", ()):
            # interface 节点本身不产生继承边，但需登记为可被 implement
            pass

        # 递归
        for child in node.children:
            self._walk_for_edges(
                node=child, source_bytes=source_bytes, language=language,
                rel_types=rel_types, module_id=module_id,
                local_symbols=local_symbols, symbol_by_name=symbol_by_name,
                qualified_by_suffix=qualified_by_suffix,
                module_by_basename=module_by_basename,
                edges=edges, edge_seen=edge_seen,
            )

    # ------------------------------------------------------------------
    # 各类边的具体提取逻辑
    # ------------------------------------------------------------------
    def _add_import_edge(
        self, node, source_bytes: bytes, language: str, module_id: str,
        module_by_basename: dict[str, list[str]],
        edges: list[GraphEdge], edge_seen: set[tuple[str, str, str]],
    ) -> None:
        """提取 import 边：module -> 被引用的 module（仅命中仓库内文件）。"""
        imported_names = self._extract_imported_names(node, source_bytes, language)
        for name in imported_names:
            # 取 basename：from foo.bar.baz import x -> 尝试 baz / foo / bar.baz
            candidates = [name, name.split(".")[-1], name.split("/")[-1].replace(".py", "")]
            for cand in candidates:
                if not cand:
                    continue
                targets = module_by_basename.get(cand) or module_by_basename.get(cand.replace("-", "_"))
                if targets:
                    for target_id in targets:
                        if target_id == module_id:
                            continue
                        self._add_edge(
                            edges=edges, edge_seen=edge_seen,
                            source=module_id, target=target_id, edge_type=EdgeType.IMPORT,
                        )
                    break  # 命中一个即可

    def _add_call_edge(
        self, node, source_bytes: bytes, language: str, caller_id: str,
        symbol_by_name: dict[str, list[str]],
        qualified_by_suffix: dict[str, list[str]],
        edges: list[GraphEdge], edge_seen: set[tuple[str, str, str]],
    ) -> None:
        """提取 call 边：caller_function -> 被调用的 function（尽力匹配）。"""
        callee_name = self._extract_callee_name(node, source_bytes, language)
        if not callee_name:
            return
        # 内置/匿名调用过滤
        if callee_name in {"print", "len", "range", "str", "int", "float", "list",
                           "dict", "set", "tuple", "bool", "type", "isinstance",
                           "super", "self", "console", "require"}:
            return

        target_id = self._resolve_symbol_target(callee_name, symbol_by_name, qualified_by_suffix)
        if target_id and target_id != caller_id:
            self._add_edge(
                edges=edges, edge_seen=edge_seen,
                source=caller_id, target=target_id, edge_type=EdgeType.CALL,
            )

    def _add_inherit_edges(
        self, node, source_bytes: bytes, language: str, file_module_id: str,
        symbol_by_name: dict[str, list[str]],
        qualified_by_suffix: dict[str, list[str]],
        edges: list[GraphEdge], edge_seen: set[tuple[str, str, str]],
    ) -> None:
        """提取 inherit / implement 边：class -> 父类 / 接口。"""
        # 找到本类的节点 ID
        class_name = self._extract_class_name(node, source_bytes, language)
        if not class_name:
            return
        class_id = self._resolve_symbol_target(class_name, symbol_by_name, qualified_by_suffix)
        if not class_id:
            return

        parents, interfaces = self._extract_parents(node, source_bytes, language)
        for parent in parents:
            target = self._resolve_symbol_target(parent, symbol_by_name, qualified_by_suffix)
            if target and target != class_id:
                self._add_edge(
                    edges=edges, edge_seen=edge_seen,
                    source=class_id, target=target, edge_type=EdgeType.INHERIT,
                )
        for iface in interfaces:
            target = self._resolve_symbol_target(iface, symbol_by_name, qualified_by_suffix)
            if target and target != class_id:
                self._add_edge(
                    edges=edges, edge_seen=edge_seen,
                    source=class_id, target=target, edge_type=EdgeType.IMPLEMENT,
                )

    # ------------------------------------------------------------------
    # 名称提取辅助
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_imported_names(node, source_bytes: bytes, language: str) -> list[str]:
        """从 import 节点提取被引用的模块名。"""
        text = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="replace")
        names: list[str] = []
        if language == "python":
            # import a.b.c / from a.b import c
            if text.startswith("from "):
                m = text.split()
                if len(m) >= 2:
                    names.append(m[1])
            elif text.startswith("import "):
                # import a, b.c -> [a, b.c]
                body = text[len("import "):].strip()
                for part in body.split(","):
                    part = part.strip().split(" as ")[0].strip()
                    if part:
                        names.append(part)
        elif language in ("javascript", "typescript", "tsx"):
            # import X from './path' / import { a } from 'mod'
            import re
            m = re.search(r"from\s+['\"]([^'\"]+)['\"]", text)
            if m:
                names.append(m.group(1))
            else:
                m = re.search(r"import\s+['\"]([^'\"]+)['\"]", text)
                if m:
                    names.append(m.group(1))
        elif language == "java":
            # import x.y.Z;
            m = text.replace(";", "").replace("import ", "").replace("static ", "").strip()
            if m:
                names.append(m)
        elif language == "go":
            import re
            for m in re.finditer(r'"([^"]+)"', text):
                names.append(m.group(1).split("/")[-1])
        elif language == "rust":
            # use a::b::c;
            body = text.replace("use ", "").replace(";", "").strip()
            body = body.split("{")[0].strip()
            if body:
                names.append(body.split("::")[-1])
        return names

    @staticmethod
    def _extract_callee_name(node, source_bytes: bytes, language: str) -> str | None:
        """从调用表达式提取被调用者名称。"""
        # call 表达式的 function 字段通常是标识符或成员访问
        func_node = node.child_by_field_name("function") or node.child_by_field_name("callee")
        if func_node is None:
            # 回退：取第一个 identifier 子节点
            for child in node.children:
                if child.type in ("identifier", "field_access", "member_expression",
                                  "attribute", "property_identifier"):
                    func_node = child
                    break
        if func_node is None:
            return None
        text = source_bytes[func_node.start_byte:func_node.end_byte].decode("utf-8", errors="replace")
        # obj.method -> method; module.func -> func
        return text.split(".")[-1].strip()

    @staticmethod
    def _extract_class_name(node, source_bytes: bytes, language: str) -> str | None:
        name_node = node.child_by_field_name("name")
        if name_node is None:
            for child in node.children:
                if child.type == "identifier" or child.type == "type_identifier":
                    name_node = child
                    break
        if name_node is None:
            return None
        return source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace")

    @staticmethod
    def _extract_parents(node, source_bytes: bytes, language: str) -> tuple[list[str], list[str]]:
        """提取父类与接口列表。返回 (parents, interfaces)。"""
        parents: list[str] = []
        interfaces: list[str] = []
        if language == "python":
            # argument_list 中的标识符
            args = node.child_by_field_name("superclasses")
            if args is not None:
                for child in args.children:
                    if child.type in ("identifier", "attribute", "type_identifier"):
                        text = source_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
                        parents.append(text.split(".")[-1])
        elif language in ("javascript", "typescript", "tsx"):
            # heritage: extends X, implements Y, Z
            for child in node.children:
                if child.type == "class_heritage":
                    text = source_bytes[child.start_byte:child.end_byte].decode("utf-8", errors="replace")
                    if text.startswith("extends"):
                        body = text[len("extends"):].strip()
                        parents.append(body.split("<")[0].strip())
                    elif text.startswith("implements"):
                        body = text[len("implements"):].strip()
                        for part in body.split(","):
                            interfaces.append(part.strip().split("<")[0].strip())
        elif language == "java":
            # superclass / interfaces 字段
            sup = node.child_by_field_name("superclass")
            if sup is not None:
                text = source_bytes[sup.start_byte:sup.end_byte].decode("utf-8", errors="replace")
                parents.append(text)
            ifs = node.child_by_field_name("interfaces")
            if ifs is not None:
                text = source_bytes[ifs.start_byte:ifs.end_byte].decode("utf-8", errors="replace")
                # 去除 implements 前缀
                body = text.replace("implements", "").strip()
                for part in body.split(","):
                    interfaces.append(part.strip())
        return parents, interfaces

    # ------------------------------------------------------------------
    # 解析辅助
    # ------------------------------------------------------------------
    @staticmethod
    def _find_containing_symbol(byte_offset: int, local_symbols: list[tuple[int, int, str, NodeType]]) -> str | None:
        """根据字节偏移找到包含该位置的符号节点 ID。"""
        for start, end, nid, _ in local_symbols:
            if start <= byte_offset < end:
                return nid
        return None

    @staticmethod
    def _resolve_symbol_target(
        name: str,
        symbol_by_name: dict[str, list[str]],
        qualified_by_suffix: dict[str, list[str]],
    ) -> str | None:
        """解析符号引用到节点 ID。优先全限定名后缀匹配，再按符号名。"""
        if not name:
            return None
        # 1) 精确符号名匹配
        ids = symbol_by_name.get(name)
        if ids:
            return ids[0]
        # 2) 全限定名后缀匹配（如调用 self.foo -> foo）
        ids = qualified_by_suffix.get(name)
        if ids:
            return ids[0]
        # 3) 取末尾段再试
        last = name.split(".")[-1]
        ids = symbol_by_name.get(last)
        if ids:
            return ids[0]
        ids = qualified_by_suffix.get(last)
        if ids:
            return ids[0]
        return None

    @staticmethod
    def _add_edge(
        edges: list[GraphEdge],
        edge_seen: set[tuple[str, str, str]],
        source: str,
        target: str,
        edge_type: EdgeType,
    ) -> None:
        key = (source, target, edge_type.value)
        if key in edge_seen:
            return
        edge_seen.add(key)
        edges.append(GraphEdge(
            id=f"{edge_type.value}-{source}->{target}",
            source=source, target=target, type=edge_type,
        ))

    # ------------------------------------------------------------------
    # 调用链提取（供时序图使用）
    # ------------------------------------------------------------------
    def extract_call_chain(
        self,
        files_info: list[FileInfo],
        entry_function: str,
        repo_url: str = "",
        max_depth: int = 5,
        repo_path: Path | str | None = None,
    ) -> SequenceData:
        """从入口函数出发提取调用链，生成时序图数据。

        Args:
            files_info: 解析结果
            entry_function: 入口函数名（symbol_name 或 qualified_name）
            repo_url: 仓库地址
            max_depth: 最大调用深度
            repo_path: 本地仓库根目录，透传给 extract 以读取原始文件

        Returns:
            SequenceData: 时序图数据 + Mermaid 语法
        """
        start = time.perf_counter()

        # 先构建完整依赖图以获取 call 边
        graph = self.extract(files_info, repo_url=repo_url, repo_path=repo_path)

        # 构建邻接表：caller_id -> [(callee_id, callee_label)]
        call_adj: dict[str, list[tuple[str, str]]] = defaultdict(list)
        node_by_id = {n.id: n for n in graph.nodes}
        for edge in graph.edges:
            if edge.type == EdgeType.CALL:
                callee = node_by_id.get(edge.target)
                if callee:
                    call_adj[edge.source].append((edge.target, callee.label))

        # 找到入口函数节点
        entry_id = self._resolve_symbol_target(
            entry_function,
            {n.label: [n.id] for n in graph.nodes if n.type == NodeType.FUNCTION},
            {n.qualified_name or n.label: [n.id] for n in graph.nodes},
        )
        if not entry_id:
            # 回退：按 label 模糊匹配
            for n in graph.nodes:
                if n.type == NodeType.FUNCTION and entry_function in (n.label, n.qualified_name or ""):
                    entry_id = n.id
                    break

        participants: list[SequenceParticipant] = []
        messages: list[SequenceMessage] = []
        visited: set[str] = set()
        participant_ids: set[str] = set()

        def _ensure_participant(nid: str) -> str:
            if nid not in participant_ids:
                node = node_by_id.get(nid)
                if node:
                    participants.append(SequenceParticipant(
                        id=nid, name=node.label,
                        type="actor" if nid == entry_id else "participant",
                    ))
                    participant_ids.add(nid)
            return nid

        def _bfs(start_id: str) -> None:
            queue: list[tuple[str, int]] = [(start_id, 0)]
            msg_idx = 0
            while queue:
                cur_id, depth = queue.pop(0)
                if depth >= max_depth or cur_id in visited:
                    continue
                visited.add(cur_id)
                _ensure_participant(cur_id)
                for callee_id, callee_label in call_adj.get(cur_id, []):
                    _ensure_participant(callee_id)
                    msg_idx += 1
                    messages.append(SequenceMessage(
                        id=f"m{msg_idx}",
                        **{"from": cur_id, "to": callee_id},
                        label=f"调用 {callee_label}()",
                        kind="message",
                    ))
                    if callee_id not in visited:
                        queue.append((callee_id, depth + 1))

        if entry_id:
            _bfs(entry_id)
        else:
            logger.warning(f"未找到入口函数: {entry_function}")

        mermaid_syntax = self._build_mermaid_sequence(participants, messages, entry_function)

        elapsed = time.perf_counter() - start
        logger.info(
            f"调用链提取完成: 入口={entry_function} 参与者={len(participants)} "
            f"消息={len(messages)} 耗时={elapsed:.3f}s"
        )
        return SequenceData(
            title=f"调用链: {entry_function}",
            participants=participants,
            messages=messages,
            mermaid_syntax=mermaid_syntax,
            repo_url=repo_url,
            entry_function=entry_function,
            elapsed_seconds=elapsed,
        )

    @staticmethod
    def _build_mermaid_sequence(
        participants: list[SequenceParticipant],
        messages: list[SequenceMessage],
        title: str,
    ) -> str:
        """生成 Mermaid sequenceDiagram 语法字符串。"""
        lines = ["sequenceDiagram"]
        lines.append(f"    title {title}")
        for p in participants:
            lines.append(f"    participant {p.id} as {p.name}")
        for m in messages:
            lines.append(f"    {m.from_participant}->>{m.to_participant}: {m.label}")
        return "\n".join(lines)


call_graph_extractor = CallGraphExtractor()
