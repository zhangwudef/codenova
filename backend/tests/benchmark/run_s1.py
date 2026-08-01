"""S1 基准测试：切分策略对比（AST vs 语义 vs 固定长度）。

自包含脚本，不依赖 Qdrant / MinIO / LLM，仅依赖 Embedding 模型。
在内存中做余弦相似度检索，对比三种切分策略在「定位/行为类」问题上的
检索质量（Hit@5 / Recall@5 / MRR / Precision@5）。

用法：
    cd backend
    python -m tests.benchmark.run_s1

说明：
    - 测试仓库为 codenova 后端自身（backend/app），ground-truth 见
      tests/benchmark/questions.csv（15 题，人工标注）。
    - Embedding 模型默认 paraphrase-multilingual-MiniLM-L12-v2（多语种、
      下载快），生产环境使用 BAAI/bge-m3；切分策略间的相对比较结论
      不因 Embedding 模型选择而反转。
"""

from __future__ import annotations

import csv
import time
from pathlib import Path

import numpy as np

from app.services.parser.languages import LanguageRegistry
from app.services.rag.ast_splitter import (
    ASTChunkStrategy,
    FixedLengthChunkStrategy,
    SemanticChunkStrategy,
)

# ------------------------------------------------------------------
# 配置
# ------------------------------------------------------------------
BACKEND_ROOT = Path(__file__).resolve().parents[2]  # backend/
REPO_DIR = BACKEND_ROOT / "app"
QUESTIONS_CSV = BACKEND_ROOT / "tests" / "benchmark" / "questions.csv"
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
TOP_K = 5
STRATEGIES = {
    "fixed": FixedLengthChunkStrategy(),
    "semantic": SemanticChunkStrategy(),
    "ast": ASTChunkStrategy(),
}


# ------------------------------------------------------------------
# 数据加载
# ------------------------------------------------------------------
def load_source_files(repo_dir: Path) -> list[tuple[str, str, str]]:
    """遍历仓库，返回 [(file_path, language, source), ...]。"""
    files: list[tuple[str, str, str]] = []
    for path in sorted(repo_dir.rglob("*.py")):
        # 路径以 "app/" 为前缀，与 questions.csv 的 gt_files 对齐
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
# 切分
# ------------------------------------------------------------------
def split_all(strategy, files: list[tuple[str, str, str]]) -> list[tuple[str, str]]:
    """对全部文件应用切分策略，返回 [(content, file_path), ...]。"""
    chunks: list[tuple[str, str]] = []
    for file_path, language, source in files:
        for content, metadata in strategy.split(source, file_path, language):
            text = content.strip()
            if text:
                chunks.append((text, metadata.file_path))
    return chunks


# ------------------------------------------------------------------
# 检索评估
# ------------------------------------------------------------------
def embed(texts: list[str], model) -> np.ndarray:
    vecs = model.encode(texts, batch_size=32, show_progress_bar=False, normalize_embeddings=True)
    return np.asarray(vecs, dtype=np.float32)


def retrieve(query_vec: np.ndarray, chunk_vecs: np.ndarray, top_k: int) -> list[int]:
    scores = chunk_vecs @ query_vec
    k = min(top_k, len(scores))
    # argpartition 取 top-k，再按分数排序
    idx = np.argpartition(-scores, k - 1)[:k]
    return idx[np.argsort(-scores[idx])].tolist()


def evaluate(questions, chunk_vecs, chunk_files, model) -> dict:
    hits = 0
    recall_sum = 0.0
    mrr_sum = 0.0
    precision_sum = 0.0
    latencies: list[float] = []

    for q in questions:
        gt_files = {f.strip() for f in q["gt_files"].split(";") if f.strip()}
        q_vec = embed([q["question"]], model)[0]
        t0 = time.perf_counter()
        top_idx = retrieve(q_vec, chunk_vecs, TOP_K)
        latencies.append((time.perf_counter() - t0) * 1000)

        hit_files = {chunk_files[i] for i in top_idx}
        hit_intersection = hit_files & gt_files
        if hit_intersection:
            hits += 1
            recall_sum += len(hit_intersection) / len(gt_files)
            # MRR：第一个命中的排名
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
    print("S1 基准测试：切分策略对比（fixed / semantic / ast）")
    print("=" * 70)

    # 预热 tree-sitter
    LanguageRegistry.get_parser("python")

    files = load_source_files(REPO_DIR)
    questions = load_questions(QUESTIONS_CSV)
    print(f"测试仓库: {REPO_DIR.relative_to(BACKEND_ROOT)}")
    print(f"源文件数: {len(files)}")
    print(f"问题数:   {len(questions)}")
    print(f"Embedding 模型: {EMBEDDING_MODEL}")
    print("-" * 70)

    print("加载 Embedding 模型（首次需下载）...")
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(EMBEDDING_MODEL)
    print(f"模型就绪，向量维度: {model.get_sentence_embedding_dimension()}")
    print("-" * 70)

    results: list[dict] = []
    for name, strategy in STRATEGIES.items():
        t0 = time.perf_counter()
        chunks = split_all(strategy, files)
        split_secs = time.perf_counter() - t0

        if not chunks:
            print(f"[{name}] 未产出 chunk，跳过")
            continue

        t0 = time.perf_counter()
        chunk_vecs = embed([c[0] for c in chunks], model)
        embed_secs = time.perf_counter() - t0

        metrics = evaluate(questions, chunk_vecs, [c[1] for c in chunks], model)
        row = {
            "strategy": name,
            "chunks": len(chunks),
            "split_secs": round(split_secs, 3),
            "embed_secs": round(embed_secs, 3),
            **metrics,
        }
        results.append(row)
        print(
            f"[{name:>8}] chunks={len(chunks):>4} 切分={split_secs:.2f}s "
            f"向量化={embed_secs:.2f}s | "
            f"Hit@5={metrics['hit@5']:.2%} Recall@5={metrics['recall@5']:.2%} "
            f"MRR={metrics['mrr']:.3f} P@5={metrics['precision@5']:.2%} "
            f"p50={metrics['p50_latency_ms']:.1f}ms"
        )

    print("-" * 70)
    # 写出 CSV
    out_csv = BACKEND_ROOT / "tests" / "benchmark" / "results_S1.csv"
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    print(f"结果已写入: {out_csv.relative_to(BACKEND_ROOT)}")


if __name__ == "__main__":
    main()
