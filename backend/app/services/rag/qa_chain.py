"""LangChain RAG 问答链。

基于 LangChain LCEL 构建完整的问答处理链：
用户查询 → 向量检索 → 上下文构建 → 答案生成。

支持流式输出（文档 3.1 节「流式打字机效果」）与文档生成结合 RAG 检索（文档 2.1 节）。
"""

from __future__ import annotations

import time
from collections.abc import Generator

from loguru import logger

from app.core.config import settings
from app.services.rag.schemas import (
    QAAnswer,
    QAQuestion,
    RetrievedChunk,
)
from app.services.rag.vector_store import VectorStoreService


class RAGChain:
    """RAG 问答链。

    封装完整的检索增强生成流程：
    1. 查询向量化
    2. 相似文档检索
    3. 上下文信息整合
    4. 大语言模型调用
    5. 返回带源码定位的答案
    """

    def __init__(
        self,
        vector_store: VectorStoreService | None = None,
        llm_model: str | None = None,
    ) -> None:
        self._vector_store = vector_store
        self.llm_model = llm_model or settings.llm_model
        self._llm = None
        self._chain = None
        self._graph_cache: dict[str, object] = {}  # repo_url -> GraphData

    @property
    def vector_store(self) -> VectorStoreService:
        """获取向量存储实例（惰性加载）。"""
        if self._vector_store is None:
            from app.services.rag.vector_store import VectorStoreService
            self._vector_store = VectorStoreService()
        return self._vector_store

    def _get_graph(self, repo_url: str | None):
        """获取调用关系图（带缓存，文档 4.1 节双索引策略）。"""
        if not repo_url:
            return None
        if repo_url in self._graph_cache:
            return self._graph_cache[repo_url]
        try:
            from app.services.rag.graph_store import graph_store_service
            graph = graph_store_service.load(repo_url)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"图索引加载失败: {e}")
            graph = None
        self._graph_cache[repo_url] = graph
        return graph

    def _expand_with_graph(
        self, chunks: list[RetrievedChunk], repo_url: str | None, max_depth: int = 1
    ) -> list[RetrievedChunk]:
        """基于图索引对语义检索结果做 1 跳扩展（文档 4.1 节）。

        将扩展节点的元信息作为补充上下文追加到 chunks 末尾。
        """
        graph = self._get_graph(repo_url)
        if not graph or not chunks:
            return chunks

        try:
            from app.services.rag.graph_store import graph_store_service
            # 用 qualified_name 匹配图节点
            qualified_names = [
                c.metadata.qualified_name for c in chunks if c.metadata.qualified_name
            ]
            if not qualified_names:
                return chunks

            seed_nodes = graph_store_service.find_nodes_by_qualified_name(
                graph, qualified_names
            )
            if not seed_nodes:
                return chunks

            seed_ids = [n.id for n in seed_nodes]
            expanded = graph_store_service.expand(
                graph, seed_ids, max_depth=max_depth,
                edge_types={"call", "inherit", "implement"},
            )

            if not expanded:
                return chunks

            # 将扩展节点转换为轻量 RetrievedChunk（仅含元信息，标记为图扩展来源）
            from app.services.rag.schemas import ChunkType, CodeChunkMetadata
            existing_qn = {c.metadata.qualified_name for c in chunks}
            extra_chunks: list[RetrievedChunk] = []
            for node in expanded:
                if not node.qualified_name or node.qualified_name in existing_qn:
                    continue
                meta = CodeChunkMetadata(
                    file_path=node.file_path,
                    language="unknown",
                    chunk_type=ChunkType.FUNCTION,
                    symbol_name=node.label,
                    qualified_name=node.qualified_name,
                    start_line=node.start_line,
                    end_line=node.end_line,
                    repo_url=repo_url,
                    extra={"graph_expanded": True, "node_type": node.type.value},
                )
                extra_chunks.append(RetrievedChunk(
                    content=f"[图扩展节点] {node.type.value}: {node.qualified_name}",
                    metadata=meta,
                    score=0.0,
                ))
            logger.info(f"图扩展: seed={len(seed_ids)} expanded={len(extra_chunks)}")
            return chunks + extra_chunks
        except Exception as e:  # noqa: BLE001 - 图扩展失败降级
            logger.debug(f"图扩展失败，降级纯语义检索: {e}")
            return chunks

    def _get_llm(self):
        """获取 LLM 实例。"""
        if self._llm is None:
            try:
                from langchain_openai import ChatOpenAI

                self._llm = ChatOpenAI(
                    model=self.llm_model,
                    temperature=0.1,
                    base_url=settings.openai_base_url,
                    api_key=settings.openai_api_key,
                )
                logger.info(f"LLM 初始化完成: {self.llm_model}")
            except Exception as e:
                logger.error(f"LLM 初始化失败: {e}")
                raise
        return self._llm

    def ask(self, question: QAQuestion) -> QAAnswer:
        """执行问答流程。

        Args:
            question: 问答请求

        Returns:
            问答响应（含答案和源码来源）
        """
        start_time = time.perf_counter()

        # Step 1: 向量检索
        logger.info(f"执行向量检索: {question.question[:50]}...")
        retrieved_chunks = self.vector_store.search(
            query=question.question,
            top_k=question.top_k,
            score_threshold=question.score_threshold,
            repo_url=question.repo_url,
        )

        if not retrieved_chunks:
            elapsed = time.perf_counter() - start_time
            return QAAnswer(
                answer="抱歉，未能在代码库中找到与您问题相关的内容。请尝试调整问题描述或确认相关代码已正确索引。",
                sources=[],
                question=question.question,
                model=self.llm_model,
                latency_ms=elapsed * 1000,
            )

        # Step 1.5: 图索引扩展（双索引策略，文档 4.1 节）
        retrieved_chunks = self._expand_with_graph(retrieved_chunks, question.repo_url)

        # Step 2: 构建上下文
        context = self._build_context(retrieved_chunks)

        # Step 3: 生成答案
        answer = self._generate_answer(question.question, context, retrieved_chunks)

        elapsed = time.perf_counter() - start_time

        return QAAnswer(
            answer=answer,
            sources=retrieved_chunks[:question.top_k],
            question=question.question,
            model=self.llm_model,
            latency_ms=elapsed * 1000,
        )

    def ask_stream(self, question: QAQuestion) -> Generator[dict, None, None]:
        """流式问答（文档 3.1 节「流式打字机效果」）。

        生成器，按事件类型 yield 字典：
          - {"type": "sources", "sources": [...]}  检索完成，推送来源
          - {"type": "delta", "content": "..."}     增量文本片段
          - {"type": "done", "answer": QAAnswer}    完成，推送完整答案
          - {"type": "error", "message": "..."}     错误

        Args:
            question: 问答请求

        Yields:
            事件字典
        """
        start_time = time.perf_counter()

        # Step 1: 向量检索
        logger.info(f"流式问答-执行向量检索: {question.question[:50]}...")
        retrieved_chunks = self.vector_store.search(
            query=question.question,
            top_k=question.top_k,
            score_threshold=question.score_threshold,
            repo_url=question.repo_url,
        )

        if not retrieved_chunks:
            elapsed = time.perf_counter() - start_time
            yield {
                "type": "done",
                "answer": QAAnswer(
                    answer="抱歉，未能在代码库中找到与您问题相关的内容。请尝试调整问题描述或确认相关代码已正确索引。",
                    sources=[],
                    question=question.question,
                    model=self.llm_model,
                    latency_ms=elapsed * 1000,
                ),
            }
            return

        # 推送来源信息
        yield {"type": "sources", "sources": retrieved_chunks[:question.top_k]}

        # Step 1.5: 图索引扩展（双索引策略，文档 4.1 节）
        retrieved_chunks = self._expand_with_graph(retrieved_chunks, question.repo_url)

        # Step 2: 构建上下文
        context = self._build_context(retrieved_chunks)

        # Step 3: 流式生成答案
        full_answer = ""
        try:
            llm = self._get_llm()
            prompt = self._build_prompt(question.question, context)

            for chunk in llm.stream(prompt):
                delta = chunk.content if hasattr(chunk, "content") else str(chunk)
                if delta:
                    full_answer += delta
                    yield {"type": "delta", "content": delta}

            # 追加来源摘要
            source_summary = self._format_source_summary(retrieved_chunks)
            if source_summary:
                tail = f"\n\n---\n**相关代码位置:**\n{source_summary}"
                full_answer += tail
                yield {"type": "delta", "content": tail}

        except Exception as e:  # noqa: BLE001 - LLM 流式失败降级
            logger.error(f"LLM 流式生成失败: {e}")
            fallback = self._generate_fallback_answer(question.question, retrieved_chunks)
            full_answer = fallback
            yield {"type": "delta", "content": fallback}

        elapsed = time.perf_counter() - start_time
        yield {
            "type": "done",
            "answer": QAAnswer(
                answer=full_answer,
                sources=retrieved_chunks[:question.top_k],
                question=question.question,
                model=self.llm_model,
                latency_ms=elapsed * 1000,
            ),
        }

    def generate_doc_with_rag(
        self,
        doc_type: str,
        repo_url: str,
        module_name: str | None = None,
        top_k: int = 10,
    ) -> tuple[str, list[RetrievedChunk]]:
        """结合 RAG 检索结果生成文档（文档 2.1 节）。

        流程：按文档类型构造检索 query → 向量检索相关代码 → LLM 生成文档。

        Args:
            doc_type: readme / api / module
            repo_url: 仓库地址（用于过滤检索范围）
            module_name: 模块名（module 类型必填）
            top_k: 检索数量

        Returns:
            (生成的文档内容 Markdown, RAG 检索命中的来源代码块列表)
        """
        # 按文档类型构造检索查询
        query_map = {
            "readme": "项目入口 main 入口函数 配置 初始化 安装",
            "api": "API 路由 接口 endpoint router 请求 响应",
            "module": f"{module_name or ''} 模块 类 函数 方法 功能",
        }
        query = query_map.get(doc_type, "项目概述 功能 结构")

        logger.info(f"文档生成-RAG检索: doc_type={doc_type}, query={query[:30]}...")
        retrieved = self.vector_store.search(
            query=query, top_k=top_k, repo_url=repo_url, score_threshold=0.2,
        )

        if not retrieved:
            logger.warning("文档生成-RAG未检索到内容，回退模板生成")
            from app.services.rag.prompts import generate_document
            content = generate_document(
                doc_type=doc_type,
                project_name=repo_url.split("/")[-1] or "My Project",
                project_description="",
                module_name=module_name,
            )
            return content, []

        # 构建代码上下文摘要
        context_parts = []
        for i, chunk in enumerate(retrieved[:top_k], 1):
            meta = chunk.metadata
            loc = f"{meta.file_path}"
            if meta.start_line:
                loc += f":{meta.start_line}-{meta.end_line}"
            sym = meta.qualified_name or meta.symbol_name or ""
            context_parts.append(
                f"[{i}] {loc} ({sym})\n```{meta.language}\n{chunk.content[:800]}\n```"
            )
        code_context = "\n\n".join(context_parts)

        project_name = repo_url.split("/")[-1].replace(".git", "") or "My Project"

        # 构建文档生成 Prompt
        prompt = self._build_doc_prompt(doc_type, project_name, module_name, code_context)

        try:
            llm = self._get_llm()
            response = llm.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            return content, retrieved[:top_k]
        except Exception as e:  # noqa: BLE001
            logger.error(f"文档生成-LLM失败，降级模板: {e}")
            from app.services.rag.prompts import generate_document
            content = generate_document(
                doc_type=doc_type,
                project_name=project_name,
                project_description="",
                module_name=module_name,
            )
            return content, retrieved[:top_k]

    @staticmethod
    def _build_doc_prompt(
        doc_type: str, project_name: str, module_name: str | None, code_context: str
    ) -> str:
        """构建文档生成 Prompt。"""
        type_desc = {
            "readme": "README 文档，包含项目概述、安装指南、使用说明、项目结构",
            "api": "API 接口文档，包含接口列表、请求/响应格式、调用示例",
            "module": f"模块「{module_name or ''}」说明文档，包含功能概述、设计思路、核心方法",
        }.get(doc_type, "技术文档")

        return f"""你是一个专业的技术文档生成助手。请基于以下代码上下文，为项目生成{type_desc}。

要求：
1. 严格基于提供的代码上下文，不要编造不存在的功能
2. 使用 Markdown 格式输出
3. 内容准确、结构清晰、语言简洁
4. 引用关键代码位置时标注文件路径

代码上下文：
{code_context}

项目名称：{project_name}
请生成文档："""

    def _build_context(self, chunks: list[RetrievedChunk]) -> str:
        """构建检索上下文。"""
        context_parts = []
        for i, chunk in enumerate(chunks, 1):
            source_info = f"[来源{i}] 文件: {chunk.metadata.file_path}"
            if chunk.metadata.start_line and chunk.metadata.end_line:
                source_info += f" (第{chunk.metadata.start_line}-{chunk.metadata.end_line}行)"
            if chunk.metadata.qualified_name:
                source_info += f" 符号: {chunk.metadata.qualified_name}"

            context_parts.append(f"{source_info}\n```{'python' if chunk.metadata.language == 'python' else ''}\n{chunk.content}\n```")

        return "\n\n".join(context_parts)

    def _generate_answer(
        self, question: str, context: str, chunks: list[RetrievedChunk]
    ) -> str:
        """使用 LLM 生成答案。"""
        try:
            llm = self._get_llm()

            prompt = self._build_prompt(question, context)
            response = llm.invoke(prompt)

            answer = response.content if hasattr(response, "content") else str(response)

            source_summary = self._format_source_summary(chunks)
            if source_summary:
                answer += f"\n\n---\n**相关代码位置:**\n{source_summary}"

            return answer

        except Exception as e:  # noqa: BLE001 - LLM 服务调用容错
            logger.error(f"LLM 答案生成失败: {e}")
            return self._generate_fallback_answer(question, chunks)

    def _build_prompt(self, question: str, context: str) -> str:
        """构建提示词。"""
        prompt_template = """你是一个专业的代码助手，能够基于提供的代码上下文回答技术问题。

请严格遵循以下规则：
1. 只根据提供的上下文内容回答问题，不要编造信息
2. 如果上下文中没有相关信息，请明确说明
3. 回答时引用相关的代码片段，并标明来源文件路径
4. 使用简洁、准确的中文回答
5. 对于代码相关问题，优先给出代码示例和解释

上下文内容：
{context}

用户问题：{question}

请给出回答："""

        return prompt_template.format(context=context, question=question)

    def _format_source_summary(self, chunks: list[RetrievedChunk]) -> str:
        """格式化来源摘要。"""
        source_map: dict[str, list[RetrievedChunk]] = {}
        for chunk in chunks:
            file_path = chunk.metadata.file_path
            if file_path not in source_map:
                source_map[file_path] = []
            source_map[file_path].append(chunk)

        summary_parts = []
        for file_path, file_chunks in source_map.items():
            lines = []
            for chunk in file_chunks:
                if chunk.metadata.start_line and chunk.metadata.end_line:
                    lines.append(f"  - {chunk.metadata.start_line}-{chunk.metadata.end_line}行")
                if chunk.metadata.symbol_name:
                    lines.append(f"  - 符号: {chunk.metadata.symbol_name}")

            summary_parts.append(f"- **{file_path}**:\n" + "\n".join(lines[:2]))

        return "\n".join(summary_parts)

    def _generate_fallback_answer(
        self, question: str, chunks: list[RetrievedChunk]
    ) -> str:
        """生成降级答案（LLM 不可用时）。"""
        answer_parts = [
            f"根据您的问题「{question}」，我找到了以下相关代码片段：\n",
        ]

        for i, chunk in enumerate(chunks[:3], 1):
            answer_parts.append(f"**代码片段 {i}** (来自 {chunk.metadata.file_path}):\n")
            if chunk.metadata.start_line:
                answer_parts.append(f"位置: 第{chunk.metadata.start_line}-{chunk.metadata.end_line}行\n")
            answer_parts.append(f"```\n{chunk.content[:500]}\n```\n")

        answer_parts.append(
            "\n*注意：当前使用降级模式，建议配置 LLM 以获得更准确的回答。*"
        )

        return "\n".join(answer_parts)


class SimpleRAGService:
    """简化版 RAG 服务接口。

    提供便捷的单例访问方式，适合快速集成。
    """

    _instance: RAGChain | None = None

    @classmethod
    def get_instance(cls) -> RAGChain:
        if cls._instance is None:
            cls._instance = RAGChain()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None
