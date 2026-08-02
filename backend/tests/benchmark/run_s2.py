"""S2 基准测试：双索引 vs 纯语义检索（对应 benchmark.md §3.S2）。

固定 AST 切分，对比:
- A 组: 纯语义检索（不启用图扩展）
- B 组: 双索引检索（语义召回 + 调用关系图 1 跳扩展）

假设: B 组在「跨文件依赖」「调用链」类问题上 MRR 显著优于 A 组。

自包含运行：本地构建调用关系图，不依赖 MinIO/Qdrant/LLM。
仅依赖 sentence-transformers 与 tree-sitter。

用法:
    cd backend
    python -m tests.benchmark.run_s2

输出: tests/benchmark/results_S2.csv
"""

from __future__ import annotations

import csv
import time
from pathlib import Path

import numpy as np

from app.services.analyzer.call_graph import CallGraphExtractor
from app.services.parser.languages import LanguageRegistry
from app.services.parser.pipeline import ParsingPipeline
from app.services.parser.schemas import FileInfo
from app.services.rag.ast_splitter import ASTChunkStrategy

# ------------------------------------------------------------------
# 配置
# ------------------------------------------------------------------
BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_ROOT / "app"
QUESTIONS_CSV = BACKEND_ROOT / "tests" / "benchmark" / "questions.csv"
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
TOP_K = 5
MAX_DEPTH = 1  # 图扩展深度


# ------------------------------------------------------------------
# 数据加载
# ------------------------------------------------------------------
def load_source_files(repo_dir: Path) -> list[tuple[str, str, str]]:
    """遍历仓库，返回 [(file_path, language, source), ...]。"""
    files: list[tuple[str, str, str]] = []
    for path in sorted(repo_dir.rglob("*.py")):
        rel = "app/" + str(path.relative_to(repo_dir)).replace("\\", "/")
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        files.append((rel, "python", source))
    return files


def load_questions(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ------------------------------------------------------------------
# 切分与向量化
# ------------------------------------------------------------------
def split_all(files: list[tuple[str, str, str]]) -> list[tuple[str, str, str, str]]:
    """对全部文件应用 AST 切分。

    Returns:
        [(content, file_path, qualified_name, symbol_name), ...]
    """
    strategy = ASTChunkStrategy()
    chunks: list[tuple[str, str, str, str]] = []
    for file_path, language, source in files:
        for content, metadata in strategy.split(source, file_path, language):
            text = content.strip()
            if text:
                chunks.append((
                    text,
                    metadata.file_path,
                    metadata.qualified_name or "",
                    metadata.symbol_name or "",
                ))
    return chunks


def embed(texts: list[str], model) -> np.ndarray:
    vecs = model.encode(texts, batch_size=32, show_progress_bar=False, normalize_embeddings=True)
    return np.asarray(vecs, dtype=np.float32)


# ------------------------------------------------------------------
# 调用关系图构建
# ------------------------------------------------------------------
def build_call_graph(repo_dir: Path, files_info: list[FileInfo]):
    """构建调用关系图。"""
    extractor = CallGraphExtractor()
    graph_data = extractor.extract(
        files_info, repo_url="codenova-backend", repo_path=repo_dir
    )
    return graph_data


def build_qualified_name_index(graph_data) -> dict[str, str]:
    """qualified_name -> node_id 索引。"""
    idx: dict[str, str] = {}
    for node in graph_data.nodes:
        if node.qualified_name:
            idx[node.qualified_name] = node.id
    return idx


def build_adjacency(graph_data) -> dict[str, set[str]]:
    """node_id -> 邻居 node_id 集合（双向，仅 call/inherit/implement 边）。"""
    adj: dict[str, set[str]] = {}
    relevant_types = {"call", "inherit", "implement"}
    for edge in graph_data.edges:
        if edge.type.value not in relevant_types:
            continue
        adj.setdefault(edge.source, set()).add(edge.target)
        adj.setdefault(edge.target, set()).add(edge.source)
    return adj


# ------------------------------------------------------------------
# 检索：A 纯语义 vs B 双索引
# ------------------------------------------------------------------
def retrieve_pure_semantic(
    query_vec: np.ndarray, chunk_vecs: np.ndarray, top_k: int
) -> list[int]:
    """A 组：纯语义检索。"""
    scores = chunk_vecs @ query_vec
    k = min(top_k, len(scores))
    idx = np.argpartition(-scores, k - 1)[:k]
    return idx[np.argsort(-scores[idx])].tolist()


def retrieve_dual_index(
    query_vec: np.ndarray,
    chunk_vecs: np.ndarray,
    chunk_qualified_names: list[str],
    qn_to_node: dict[str, str],
    adjacency: dict[str, set[str]],
    node_to_qualified: dict[str, str],
    top_k: int,
    max_depth: int = 1,
) -> list[int]:
    """B 组：双索引检索 = 语义召回 + 图 1 跳扩展。

    流程:
    1. 语义召回 top_k 个 chunk
    2. 取这些 chunk 的 qualified_name，在图中找到对应节点
    3. 沿 call/inherit/implement 边 1 跳扩展
    4. 将扩展节点的 qualified_name 对应回 chunk，追加到结果末尾
       （位置靠后但参与排序重排）
    5. 综合语义分数 + 图扩展奖励重排
    """
    # Step 1: 语义召回
    scores = chunk_vecs @ query_vec
    k = min(top_k, len(scores))
    semantic_idx = np.argpartition(-scores, k - 1)[:k]
    semantic_idx = semantic_idx[np.argsort(-scores[semantic_idx])].tolist()

    # Step 2-3: 图扩展
    expanded_qns: set[str] = set()
    existing_qns = {chunk_qualified_names[i] for i in semantic_idx if chunk_qualified_names[i]}

    for i in semantic_idx:
        qn = chunk_qualified_names[i]
        if not qn:
            continue
        node_id = qn_to_node.get(qn)
        if not node_id:
            continue

        # 1 跳邻居
        neighbors = adjacency.get(node_id, set())
        # 多跳扩展
        frontier = {node_id}
        for _ in range(max_depth):
            next_frontier: set[str] = set()
            for nid in frontier:
                next_frontier.update(adjacency.get(nid, set()))
            frontier = next_frontier - {node_id}

        for nb_id in frontier:
            nb_qn = node_to_qualified.get(nb_id)
            if nb_qn and nb_qn not in existing_qns:
                expanded_qns.add(nb_qn)

    # Step 4: 将扩展 chunk 追加
    expanded_idx: list[int] = []
    qn_to_chunk_idx = {qn: i for i, qn in enumerate(chunk_qualified_names) if qn}
    for qn in expanded_qns:
        idx = qn_to_chunk_idx.get(qn)
        if idx is not None and idx not in semantic_idx:
            expanded_idx.append(idx)

    # Step 5: 重排：原 top_k 保留高分顺序，扩展项追加（图扩展奖励）
    # 简单策略：扩展项的最终位置取决于语义分数排序
    all_idx = semantic_idx + expanded_idx
    if not all_idx:
        return semantic_idx

    # 取这些位置的语义分数
    expanded_scores = [(i, scores[i]) for i in all_idx]
    # 排序：扩展项给予 0.85 的衰减系数以反映「图扩展但语义可能弱」
    reranked = sorted(
        expanded_scores,
        key=lambda x: x[1] * (1.0 if x[0] in semantic_idx else 0.85),
        reverse=True,
    )
    final_idx = [i for i, _ in reranked[:top_k]]
    return final_idx


# ------------------------------------------------------------------
# 评估
# ------------------------------------------------------------------
def evaluate(
    questions,
    chunk_vecs,
    chunk_files,
    chunk_qualified_names,
    model,
    mode: str,
    qn_to_node: dict[str, str],
    adjacency: dict[str, set[str]],
    node_to_qualified: dict[str, str],
) -> dict:
    hits = 0
    recall_sum = 0.0
    mrr_sum = 0.0
    precision_sum = 0.0
    latencies: list[float] = []

    for q in questions:
        gt_files = {f.strip() for f in q["gt_files"].split(";") if f.strip()}
        q_vec = embed([q["question"]], model)[0]
        t0 = time.perf_counter()

        if mode == "pure_semantic":
            top_idx = retrieve_pure_semantic(q_vec, chunk_vecs, TOP_K)
        else:  # dual_index
            top_idx = retrieve_dual_index(
                q_vec, chunk_vecs, chunk_qualified_names,
                qn_to_node, adjacency, node_to_qualified, TOP_K, MAX_DEPTH,
            )

        latencies.append((time.perf_counter() - t0) * 1000)

        hit_files = {chunk_files[i] for i in top_idx}
        hit_intersection = hit_files & gt_files
        if hit_intersection:
            hits += 1
            recall_sum += len(hit_intersection) / len(gt_files)
            for rank, i in enumerate(top_idx, start=1):
                if chunk_files[i] in gt_files:
                    mrr_sum += 1.0 / rank
                    break
        precision_sum += len(hit_intersection) / TOP_K

    n = len(questions)
    return {
        "hit@5": hits / n,
        "recall@5": recall_sum / n,
        "mrr": mrr_sum / n,
        "precision@5": precision_sum / n,
        "p50_latency_ms": float(np.median(latencies)),
        "p95_latency_ms": float(np.percentile(latencies, 95)),
    }


# ------------------------------------------------------------------
# 主流程
# ------------------------------------------------------------------
def main() -> None:
    print("=" * 70)
    print("S2 基准测试：双索引 vs 纯语义检索")
    print("=" * 70)

    # 预热
    LanguageRegistry.get_parser("python")

    # Step 1: 解析仓库得到 FileInfo 列表（供图构建用）
    pipeline = ParsingPipeline()
    print(f"解析仓库: {REPO_DIR.relative_to(BACKEND_ROOT)} ...")
    summary = pipeline.run(REPO_DIR, repo_url="codenova-backend", max_files=500)
    files_info = summary.files
    print(f"  解析 {len(files_info)} 文件，{summary.total_symbols} 符号")

    # Step 2: AST 切分
    files = load_source_files(REPO_DIR)
    chunks = split_all(files)
    print(f"AST 切分: {len(chunks)} chunks")

    # Step 3: 构建调用关系图
    print("构建调用关系图 ...")
    t0 = time.perf_counter()
    graph_data = build_call_graph(REPO_DIR, files_info)
    graph_secs = time.perf_counter() - t0
    print(f"  图构建完成: nodes={len(graph_data.nodes)} edges={len(graph_data.edges)} ({graph_secs:.2f}s)")

    qn_to_node = build_qualified_name_index(graph_data)
    node_to_qualified = {v: k for k, v in qn_to_node.items()}
    adjacency = build_adjacency(graph_data)

    questions = load_questions(QUESTIONS_CSV)
    print(f"问题数: {len(questions)}")
    print(f"Embedding 模型: {EMBEDDING_MODEL}")
    print("-" * 70)

    # 加载 embedding 模型
    print("加载 Embedding 模型 ...")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(EMBEDDING_MODEL)
    print(f"模型就绪，向量维度: {model.get_sentence_embedding_dimension()}")
    print("-" * 70)

    # 向量化 chunks
    chunk_contents = [c[0] for c in chunks]
    chunk_files = [c[1] for c in chunks]
    chunk_qns = [c[2] for c in chunks]
    print(f"向量化 {len(chunks)} chunks ...")
    t0 = time.perf_counter()
    chunk_vecs = embed(chunk_contents, model)
    print(f"  向量化耗时: {time.perf_counter() - t0:.2f}s")
    print("-" * 70)

    # A 组: 纯语义
    print("[A] 纯语义检索 ...")
    metrics_a = evaluate(
        questions, chunk_vecs, chunk_files, chunk_qns, model,
        "pure_semantic", qn_to_node, adjacency, node_to_qualified,
    )
    print(
        f"[A pure_semantic] Hit@5={metrics_a['hit@5']:.2%} "
        f"Recall@5={metrics_a['recall@5']:.2%} "
        f"MRR={metrics_a['mrr']:.3f} "
        f"P@5={metrics_a['precision@5']:.2%} "
        f"p50={metrics_a['p50_latency_ms']:.2f}ms"
    )

    # B 组: 双索引
    print("[B] 双索引检索（语义 + 图 1 跳扩展）...")
    metrics_b = evaluate(
        questions, chunk_vecs, chunk_files, chunk_qns, model,
        "dual_index", qn_to_node, adjacency, node_to_qualified,
    )
    print(
        f"[B dual_index]   Hit@5={metrics_b['hit@5']:.2%} "
        f"Recall@5={metrics_b['recall@5']:.2%} "
        f"MRR={metrics_b['mrr']:.3f} "
        f"P@5={metrics_b['precision@5']:.2%} "
        f"p50={metrics_b['p50_latency_ms']:.2f}ms"
    )

    # 对比
    print("-" * 70)
    print("对比（B - A）:")
    print(f"  Hit@5      Δ={metrics_b['hit@5'] - metrics_a['hit@5']:+.2%}")
    print(f"  Recall@5   Δ={metrics_b['recall@5'] - metrics_a['recall@5']:+.2%}")
    print(f"  MRR        Δ={metrics_b['mrr'] - metrics_a['mrr']:+.3f}")
    print(f"  Precision@5 Δ={metrics_b['precision@5'] - metrics_a['precision@5']:+.2%}")

    # 门槛检查（benchmark.md §7）
    mrr_diff = metrics_b['mrr'] - metrics_a['mrr']
    threshold_met = mrr_diff >= 0.10
    print(f"\n  门槛: MRR (B - A) ≥ +0.10  → {'✅ 达标' if threshold_met else '❌ 未达标'}")

    # 写出 CSV
    results = [
        {
            "strategy": "pure_semantic",
            "chunks": len(chunks),
            "graph_nodes": len(graph_data.nodes),
            "graph_edges": len(graph_data.edges),
            "graph_build_secs": round(graph_secs, 3),
            **metrics_a,
        },
        {
            "strategy": "dual_index",
            "chunks": len(chunks),
            "graph_nodes": len(graph_data.nodes),
            "graph_edges": len(graph_data.edges),
            "graph_build_secs": round(graph_secs, 3),
            **metrics_b,
        },
    ]
    out_csv = BACKEND_ROOT / "tests" / "benchmark" / "results_S2.csv"
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    print(f"\n结果已写入: {out_csv.relative_to(BACKEND_ROOT)}")


if __name__ == "__main__":
    main()
