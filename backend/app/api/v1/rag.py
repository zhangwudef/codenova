"""RAG 相关 API 接口。

提供索引构建、问答查询（含流式）、文档生成（结合 RAG）、问答固化等 RESTful 接口。
"""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.github_service import github_service
from app.services.minio_service import minio_service
from app.services.parser.pipeline import ParsingPipeline
from app.services.parser.schemas import SymbolType
from app.services.rag.ast_splitter import CodeSplitter
from app.services.rag.graph_store import graph_store_service
from app.services.rag.prompts import generate_document
from app.services.rag.qa_chain import RAGChain
from app.services.rag.schemas import (
    ChunkType,
    CodeChunkMetadata,
    DocGenerateRequest,
    DocGenerateResult,
    IndexResult,
    QAPersistRequest,
    QAPersistResult,
    QAAnswer,
    QAQuestion,
)
from app.services.rag.vector_store import VectorStoreService

router = APIRouter()


def _symbol_to_chunk_type(symbol_type: SymbolType) -> ChunkType:
    """将 SymbolType 映射到 ChunkType，补全所有类型映射。"""
    mapping: dict[SymbolType, ChunkType] = {
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
    return mapping.get(symbol_type, ChunkType.FUNCTION)


# ----------------------------------------------------------------------
# 索引状态（commit hash）持久化 helper（文档 4.1 节「增量文档更新」）
# ----------------------------------------------------------------------
def _index_state_object_name(repo_url: str) -> str:
    """生成索引状态对象名：index-state/{repo_key}.json"""
    key = (repo_url or "session").strip("/").split("/")[-1].replace(".git", "")
    return f"index-state/{key}.json"


def _save_index_commit(repo_url: str, commit: str | None) -> None:
    if not repo_url or not commit:
        return
    try:
        import json as _json
        payload = _json.dumps(
            {"repo_url": repo_url, "last_commit": commit,
             "saved_at": datetime.utcnow().isoformat()},
            ensure_ascii=False,
        )
        minio_service.put_text(
            settings.minio_bucket_docs,
            _index_state_object_name(repo_url),
            payload,
            content_type="application/json; charset=utf-8",
        )
    except Exception as e:  # noqa: BLE001
        logger.debug(f"保存索引 commit 失败: {e}")


def _load_index_commit(repo_url: str) -> str | None:
    if not repo_url:
        return None
    try:
        import json as _json
        text = minio_service.get_text(
            settings.minio_bucket_docs, _index_state_object_name(repo_url)
        )
        return _json.loads(text).get("last_commit")
    except Exception:  # noqa: BLE001
        return None


class IndexByUrlRequest(BaseModel):
    """通过 URL 索引仓库的请求。"""

    repo_url: str = Field(..., description="GitHub 仓库地址")
    branch: str | None = Field(default=None, description="分支名")
    max_files: int = Field(default=200, ge=1, le=2000)
    chunk_strategy: str = Field(default="ast", description="切分策略: ast/semantic/fixed")


@router.post("/index", response_model=IndexResult)
async def index_repo(req: IndexByUrlRequest) -> IndexResult:
    """构建仓库索引。

    流程：克隆仓库 → AST解析 → 代码切分 → Embedding向量化 → Qdrant入库
    """
    url = req.repo_url
    logger.info(f"收到索引请求: {url}")

    try:
        local_path = github_service.clone(url, branch=req.branch)
    except Exception as e:
        logger.exception("仓库克隆失败")
        raise HTTPException(status_code=422, detail=f"克隆失败: {e}") from e

    try:
        # Step 1: 解析仓库
        pipeline = ParsingPipeline()
        summary = pipeline.run(local_path, repo_url=url, max_files=req.max_files)

        # Step 2: 收集所有代码块
        all_chunks = []
        for file_info in summary.files:
            for chunk in file_info.chunks:
                metadata = CodeChunkMetadata(
                    file_path=chunk.file_path,
                    language=chunk.language,
                    chunk_type=_symbol_to_chunk_type(chunk.symbol_type),
                    symbol_name=chunk.symbol_name,
                    qualified_name=chunk.qualified_name,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    repo_url=url,
                    extra={
                        "docstring": chunk.docstring or "",
                        "line_count": chunk.line_count,
                    },
                )
                all_chunks.append((chunk.content, metadata))

        # Step 3: 向量入库
        vector_store = VectorStoreService()
        result = vector_store.index_code_chunks(all_chunks, repo_url=url)

        # Step 4: 构建调用关系图索引（文档 4.1 节「双索引策略」）
        try:
            from app.services.analyzer.call_graph import CallGraphExtractor
            graph_data = CallGraphExtractor().extract(summary.files, repo_url=url)
            graph_store_service.save(graph_data)
            logger.info(
                f"图索引构建完成: nodes={len(graph_data.nodes)}, "
                f"edges={len(graph_data.edges)}"
            )
        except Exception as e:  # noqa: BLE001 - 图索引失败不阻断主流程
            logger.warning(f"调用关系图索引构建失败（不影响语义索引）: {e}")

        # Step 5: 记录当前 commit，供下次增量索引用（文档 4.1 节）
        head_commit = github_service.get_head_commit(local_path)
        _save_index_commit(url, head_commit)

        return result

    except Exception as e:
        logger.exception("索引构建失败")
        raise HTTPException(status_code=500, detail=f"索引失败: {e}") from e
    finally:
        github_service.cleanup(local_path)


class IndexFileRequest(BaseModel):
    """索引单个文件内容的请求。"""

    content: str = Field(..., description="代码文本内容")
    file_path: str = Field(default="unknown.py", description="文件路径")
    language: str = Field(default="python", description="编程语言")
    repo_url: str = Field(default="", description="仓库地址")
    chunk_strategy: str = Field(default="ast", description="切分策略: ast/semantic/fixed")


class IndexIncrementalRequest(BaseModel):
    """增量索引请求（文档 4.1 节「增量文档更新」）。"""

    repo_url: str = Field(..., description="GitHub 仓库地址")
    branch: str | None = Field(default=None, description="分支名")
    # 上次索引的 commit；若为空则尝试从 MinIO 读取，仍为空则回退全量
    since_commit: str | None = None
    max_files: int = Field(default=500, ge=1, le=5000)


@router.post("/index-incremental")
async def index_repo_incremental(req: IndexIncrementalRequest) -> dict:
    """增量索引接口（文档 4.1 节）。

    流程：
    1. 读取上次索引 commit（since_commit 或 MinIO 中记录）
    2. 克隆最新仓库
    3. git diff 列出 added/modified/deleted 文件
    4. 仅对 added/modified 重新解析+索引；deleted 从向量库删除
    5. 更新 commit 记录

    无 since_commit 时回退到全量索引。
    """
    url = req.repo_url
    logger.info(f"收到增量索引请求: {url}, since_commit={req.since_commit}")

    # 解析 since_commit
    since_commit = req.since_commit or _load_index_commit(url)
    if not since_commit:
        logger.warning("未找到上次索引 commit，回退到全量索引")
        # 复用全量索引逻辑
        full_req = IndexByUrlRequest(
            repo_url=url, branch=req.branch, max_files=req.max_files
        )
        result = await index_repo(full_req)
        return {
            "mode": "full_fallback",
            "reason": "no_since_commit",
            "index_result": result.model_dump(mode="json"),
        }

    try:
        local_path = github_service.clone(url, branch=req.branch)
    except Exception as e:
        logger.exception("仓库克隆失败")
        raise HTTPException(status_code=422, detail=f"克隆失败: {e}") from e

    try:
        new_commit = github_service.get_head_commit(local_path)
        if not new_commit:
            raise HTTPException(status_code=500, detail="无法获取 HEAD commit")

        # 已是最新
        if new_commit == since_commit:
            return {
                "mode": "incremental",
                "since_commit": since_commit,
                "new_commit": new_commit,
                "changed_files": {"added": [], "modified": [], "deleted": [], "renamed": []},
                "message": "已是最新，无需更新",
            }

        # 获取变更文件列表
        changed = github_service.list_changed_files(local_path, since_commit, "HEAD")
        added_or_modified = list(set(changed["added"] + changed["modified"] + changed["renamed"]))
        deleted = changed["deleted"]

        logger.info(
            f"增量变更: added/modified={len(added_or_modified)}, "
            f"deleted={len(deleted)}"
        )

        # Step A: 重新解析+索引变更文件（仅对 added/modified/renamed 单独解析）
        from app.services.rag.ast_splitter import CodeSplitter
        splitter = CodeSplitter(strategy_name="ast")
        vector_store = VectorStoreService()

        reindexed_chunks = 0
        for file_path in added_or_modified:
            full_path = local_path / file_path
            if not full_path.exists() or not full_path.is_file():
                continue
            try:
                content = full_path.read_text(encoding="utf-8", errors="replace")
                # 推断语言
                ext = full_path.suffix.lstrip(".")
                language = {
                    "py": "python", "js": "javascript", "ts": "typescript",
                    "tsx": "tsx", "java": "java", "go": "go", "rs": "rust",
                }.get(ext, "unknown")
                if language == "unknown":
                    continue
                chunks = splitter.split_file(content, file_path, language)
                chunk_data = [
                    (
                        c.content,
                        CodeChunkMetadata(
                            file_path=file_path,
                            language=language,
                            chunk_type=_symbol_to_chunk_type(c.symbol_type),
                            symbol_name=c.symbol_name,
                            qualified_name=c.qualified_name,
                            start_line=c.start_line,
                            end_line=c.end_line,
                            repo_url=url,
                            extra={"docstring": c.docstring or ""},
                        ),
                    )
                    for c in chunks
                ]
                if chunk_data:
                    vector_store.index_code_chunks(chunk_data, repo_url=url)
                    reindexed_chunks += len(chunk_data)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"增量索引文件失败 {file_path}: {e}")

        # Step B: 删除已删除文件的向量（按 file_path payload 过滤）
        deleted_count = 0
        for file_path in deleted:
            try:
                # Qdrant 按 payload.file_path 删除
                from qdrant_client.http.models import Filter as QFilter, FieldCondition as QFC, MatchAny as QMA
                vector_store.qdrant.client.delete(
                    collection_name=settings.qdrant_collection_code,
                    points_selector=QFilter(must=[
                        QFC(key="file_path", match=QMA(any=[file_path])),
                    ]),
                )
                deleted_count += 1
            except Exception as e:  # noqa: BLE001
                logger.warning(f"删除文件向量失败 {file_path}: {e}")

        # Step C: 更新 commit 记录
        _save_index_commit(url, new_commit)

        return {
            "mode": "incremental",
            "since_commit": since_commit,
            "new_commit": new_commit,
            "changed_files": changed,
            "reindexed_files": len(added_or_modified),
            "reindexed_chunks": reindexed_chunks,
            "deleted_files_processed": deleted_count,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("增量索引失败")
        raise HTTPException(status_code=500, detail=f"增量索引失败: {e}") from e
    finally:
        github_service.cleanup(local_path)


@router.post("/index-file")
async def index_file(request: IndexFileRequest) -> IndexResult:
    """索引单个文件内容。

    用于直接提交代码文本进行索引。
    """
    try:
        splitter = CodeSplitter(strategy_name=request.chunk_strategy)
        chunks = splitter.split_file(request.content, request.file_path, request.language)

        vector_store = VectorStoreService()
        result = vector_store.index_code_chunks(chunks, repo_url=request.repo_url)

        return result

    except Exception as e:
        logger.exception("文件索引失败")
        raise HTTPException(status_code=500, detail=f"索引失败: {e}") from e


@router.post("/ask", response_model=QAAnswer)
async def ask_question(question: QAQuestion) -> QAAnswer:
    """问答接口。

    基于已索引的代码库进行问答。
    """
    logger.info(f"收到问答请求: {question.question[:50]}...")

    try:
        chain = RAGChain()
        answer = chain.ask(question)
        return answer
    except Exception as e:
        logger.exception("问答处理失败")
        raise HTTPException(status_code=500, detail=f"问答失败: {e}") from e


@router.post("/ask-stream")
async def ask_question_stream(question: QAQuestion) -> StreamingResponse:
    """流式问答接口（文档 3.1 节「流式打字机效果」）。

    返回 SSE 流，事件格式：
      data: {"type": "sources", "sources": [...]}
      data: {"type": "delta", "content": "..."}
      data: {"type": "done", "answer": {...}}
    """
    logger.info(f"收到流式问答请求: {question.question[:50]}...")

    def event_stream():
        chain = RAGChain()
        try:
            for event in chain.ask_stream(question):
                yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
        except Exception as e:  # noqa: BLE001
            logger.exception("流式问答异常")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/documents/generate", response_model=DocGenerateResult)
async def generate_document_api(req: DocGenerateRequest) -> DocGenerateResult:
    """文档生成接口（文档 2.1 节）。

    - 当提供 `repo_url` 时：走 RAG 增强生成（向量检索 + LLM）
    - 否则：走纯模板生成（降级方案）
    """
    logger.info(f"收到文档生成请求: type={req.doc_type}, repo_url={req.repo_url}")

    try:
        # 优先 RAG 增强
        if req.repo_url:
            chain = RAGChain()
            content, sources = chain.generate_doc_with_rag(
                doc_type=req.doc_type.value,
                repo_url=req.repo_url,
                module_name=req.module_name,
                top_k=int(req.extra_context.get("top_k", 10)),
            )
            return DocGenerateResult(
                doc_type=req.doc_type,
                content=content,
                template_used=f"{req.doc_type.value}_rag",
                used_rag=bool(sources),
                repo_url=req.repo_url,
                rag_sources=sources,
            )

        # 纯模板生成（无仓库上下文）
        content = generate_document(
            doc_type=req.doc_type.value,
            project_name=req.extra_context.get("project_name", "My Project"),
            project_description=req.extra_context.get("project_description", ""),
            module_name=req.module_name,
            **req.extra_context,
        )

        return DocGenerateResult(
            doc_type=req.doc_type,
            content=content,
            template_used=f"{req.doc_type.value}_template",
            used_rag=False,
        )

    except Exception as e:
        logger.exception("文档生成失败")
        raise HTTPException(status_code=500, detail=f"文档生成失败: {e}") from e


def _build_qa_markdown(req: QAPersistRequest) -> str:
    """将问答消息渲染为 Markdown 文档。"""
    lines: list[str] = []
    lines.append(f"# {req.title or 'CodeNova 问答沉淀'}")
    lines.append("")
    if req.repo_url:
        lines.append(f"> **仓库**: `{req.repo_url}`")
        lines.append("")
    lines.append(f"> **生成时间**: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    lines.append("")
    lines.append("---")
    lines.append("")

    for i, msg in enumerate(req.messages, 1):
        if msg.role == "user":
            lines.append(f"## Q{i // 2 + 1}: {msg.content}")
            lines.append("")
        else:
            lines.append("### A:")
            lines.append("")
            lines.append(msg.content)
            lines.append("")
            if msg.references:
                lines.append("**参考来源:**")
                lines.append("")
                for ref in msg.references:
                    loc = f"{ref.file_path}"
                    if ref.line_start and ref.line_end:
                        loc += f":L{ref.line_start}-{ref.line_end}"
                    lines.append(f"- `{loc}`")
                lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("")
    lines.append("*本文档由 CodeNova AI 「问答即文档」功能自动固化*")
    return "\n".join(lines)


@router.post("/qa/persist", response_model=QAPersistResult)
async def persist_qa_as_doc(req: QAPersistRequest) -> QAPersistResult:
    """问答固化接口（文档 4.2 节「问答即文档」）。

    将选定的问答消息渲染为 Markdown 文档并持久化到 MinIO，返回预签名下载 URL。
    """
    if not req.messages:
        raise HTTPException(status_code=422, detail="消息列表不能为空")

    logger.info(
        f"收到问答固化请求: title={req.title}, messages={len(req.messages)}, "
        f"pinned_only={req.pinned_only}"
    )

    try:
        content = _build_qa_markdown(req)

        # 对象命名：codenova-qa/{repo}/{timestamp}.md
        repo_part = (
            req.repo_url.strip("/").split("/")[-1].replace(".git", "")
            if req.repo_url
            else "session"
        )
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        object_name = f"qa/{repo_part}/{ts}.md"

        bucket = settings.minio_bucket_docs
        minio_service.put_text(bucket, object_name, content)

        try:
            download_url = minio_service.presigned_get(bucket, object_name)
        except Exception as e:  # noqa: BLE001 - 预签名失败不阻断
            logger.warning(f"预签名 URL 生成失败: {e}")
            download_url = None

        return QAPersistResult(
            object_name=object_name,
            bucket=bucket,
            download_url=download_url,
            content=content,
            message_count=len(req.messages),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("问答固化失败")
        raise HTTPException(status_code=500, detail=f"固化失败: {e}") from e


@router.get("/collections/stats")
async def get_collection_stats() -> dict:
    """获取集合统计信息。"""
    try:
        vector_store = VectorStoreService()
        code_count = vector_store.count_points()

        from app.core.config import settings
        return {
            "code_chunks_count": code_count,
            "code_collection": settings.qdrant_collection_code,
            "docs_collection": settings.qdrant_collection_docs,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取统计失败: {e}") from e


@router.delete("/collections/repo/{repo_url:path}")
async def delete_repo_data(repo_url: str) -> dict:
    """删除指定仓库的索引数据（语义索引 + 图索引）。"""
    try:
        vector_store = VectorStoreService()
        deleted = vector_store.delete_by_repo(repo_url)
        # 同步删除图索引
        graph_deleted = graph_store_service.delete(repo_url)
        return {
            "deleted_points": deleted,
            "repo_url": repo_url,
            "graph_index_deleted": graph_deleted,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {e}") from e
