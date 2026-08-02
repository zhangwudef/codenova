"""S3 基准测试：增量索引 vs 全量索引（对应 benchmark.md §3.S3）。

模拟变更（修改 5% / 15% / 30% 文件），对比:
- A 组: 全量重新索引
- B 组: 仅对变更文件重新索引

假设: 变更 ≤ 15% 时，B 组加速比 ≥ 3×。

设计:
- 本地不依赖真实 git，直接复制源文件做模拟变更
- 仅测量 AST 切分 + Embedding 向量化耗时（不含 Qdrant 入库网络 I/O）
- 测量 3 个变更比例，每个跑 3 次取中位数

用法:
    cd backend
    python -m tests.benchmark.run_s3

输出: tests/benchmark/results_S3.csv
"""

from __future__ import annotations

import csv
import shutil
import statistics
import tempfile
import time
from pathlib import Path

import numpy as np

from app.services.parser.languages import LanguageRegistry
from app.services.rag.ast_splitter import ASTChunkStrategy

# ------------------------------------------------------------------
# 配置
# ------------------------------------------------------------------
BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_ROOT / "app"
EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
CHANGE_RATIOS = [0.05, 0.15, 0.30]
RUNS = 3  # 每组测试重复次数


# ------------------------------------------------------------------
# 仓库准备
# ------------------------------------------------------------------
def collect_source_files(repo_dir: Path) -> list[Path]:
    """收集仓库内所有 .py 文件。"""
    return sorted(p for p in repo_dir.rglob("*.py") if p.is_file())


def full_index(files: list[Path], strategy: ASTChunkStrategy, model) -> tuple[int, float, float]:
    """全量索引: 切分 + 向量化。返回 (chunks, split_secs, embed_secs)。"""
    t0 = time.perf_counter()
    all_chunks: list[str] = []
    for path in files:
        source = path.read_text(encoding="utf-8", errors="replace")
        rel = str(path.relative_to(REPO_DIR)).replace("\\", "/")
        for content, _ in strategy.split(source, rel, "python"):
            text = content.strip()
            if text:
                all_chunks.append(text)
    split_secs = time.perf_counter() - t0

    t0 = time.perf_counter()
    if all_chunks:
        vecs = model.encode(
            all_chunks, batch_size=32, show_progress_bar=False, normalize_embeddings=True
        )
    else:
        vecs = np.array([])
    embed_secs = time.perf_counter() - t0

    return len(all_chunks), split_secs, embed_secs


def incremental_index(
    files: list[Path],
    changed_indices: set[int],
    strategy: ASTChunkStrategy,
    model,
    existing_chunks_count: int = 0,
) -> tuple[int, float, float, int]:
    """增量索引: 仅对 changed_indices 中的文件切分 + 向量化。

    Returns:
        (chunks_reprocessed, split_secs, embed_secs, files_skipped)
    """
    t0 = time.perf_counter()
    new_chunks: list[str] = []
    files_skipped = 0
    for i, path in enumerate(files):
        if i not in changed_indices:
            files_skipped += 1
            continue
        source = path.read_text(encoding="utf-8", errors="replace")
        rel = str(path.relative_to(REPO_DIR)).replace("\\", "/")
        for content, _ in strategy.split(source, rel, "python"):
            text = content.strip()
            if text:
                new_chunks.append(text)
    split_secs = time.perf_counter() - t0

    t0 = time.perf_counter()
    if new_chunks:
        vecs = model.encode(
            new_chunks, batch_size=32, show_progress_bar=False, normalize_embeddings=True
        )
    else:
        vecs = np.array([])
    embed_secs = time.perf_counter() - t0

    return len(new_chunks), split_secs, embed_secs, files_skipped


def select_changed_files(total: int, ratio: float, seed: int = 42) -> set[int]:
    """按比例随机选择变更文件索引。"""
    n_change = max(1, int(total * ratio))
    rng = np.random.default_rng(seed)
    return set(int(i) for i in rng.choice(total, size=n_change, replace=False))


# ------------------------------------------------------------------
# 主流程
# ------------------------------------------------------------------
def main() -> None:
    print("=" * 70)
    print("S3 基准测试：增量索引 vs 全量索引")
    print("=" * 70)

    LanguageRegistry.get_parser("python")

    files = collect_source_files(REPO_DIR)
    print(f"测试仓库: {REPO_DIR.relative_to(BACKEND_ROOT)}")
    print(f"源文件数: {len(files)}")
    print(f"Embedding 模型: {EMBEDDING_MODEL}")
    print(f"变更比例: {CHANGE_RATIOS}")
    print(f"每组重复: {RUNS} 次取中位数")
    print("-" * 70)

    print("加载 Embedding 模型 ...")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(EMBEDDING_MODEL)
    print(f"模型就绪，向量维度: {model.get_sentence_embedding_dimension()}")
    print("-" * 70)

    strategy = ASTChunkStrategy()

    # 预热: 跑一次全量索引
    print("预热全量索引 ...")
    warm_chunks, _, _ = full_index(files, strategy, model)
    print(f"  全量产出 {warm_chunks} chunks")
    print("-" * 70)

    results: list[dict] = []

    for ratio in CHANGE_RATIOS:
        changed = select_changed_files(len(files), ratio)
        n_changed = len(changed)
        print(f"\n变更比例 {ratio:.0%}（{n_changed} / {len(files)} 文件）:")

        # A 组: 全量索引（重复 RUNS 次）
        full_times: list[float] = []
        full_split_times: list[float] = []
        full_embed_times: list[float] = []
        for run in range(RUNS):
            t0 = time.perf_counter()
            n_chunks, split_s, embed_s = full_index(files, strategy, model)
            total = time.perf_counter() - t0
            full_times.append(total)
            full_split_times.append(split_s)
            full_embed_times.append(embed_s)
            print(f"  [A full] run#{run+1}: total={total:.2f}s split={split_s:.2f}s embed={embed_s:.2f}s")

        # B 组: 增量索引（重复 RUNS 次）
        incr_times: list[float] = []
        incr_split_times: list[float] = []
        incr_embed_times: list[float] = []
        for run in range(RUNS):
            t0 = time.perf_counter()
            n_new, split_s, embed_s, n_skip = incremental_index(
                files, changed, strategy, model, existing_chunks_count=warm_chunks
            )
            total = time.perf_counter() - t0
            incr_times.append(total)
            incr_split_times.append(split_s)
            incr_embed_times.append(embed_s)
            print(
                f"  [B incr] run#{run+1}: total={total:.2f}s "
                f"split={split_s:.2f}s embed={embed_s:.2f}s "
                f"reprocessed={n_new} skipped={n_skip}"
            )

        # 中位数
        full_median = statistics.median(full_times)
        incr_median = statistics.median(incr_times)
        speedup = full_median / incr_median if incr_median > 0 else float("inf")

        print(f"\n  中位数: full={full_median:.2f}s  incr={incr_median:.2f}s  speedup={speedup:.2f}x")

        # 门槛检查（benchmark.md §7）
        if ratio <= 0.15:
            threshold_met = speedup >= 3.0
            print(f"  门槛: 变更 ≤ 15% 时加速比 ≥ 3×  → {'✅ 达标' if threshold_met else '❌ 未达标'}")

        results.append({
            "change_ratio": ratio,
            "total_files": len(files),
            "changed_files": n_changed,
            "full_total_secs_median": round(full_median, 3),
            "full_split_secs_median": round(statistics.median(full_split_times), 3),
            "full_embed_secs_median": round(statistics.median(full_embed_times), 3),
            "incr_total_secs_median": round(incr_median, 3),
            "incr_split_secs_median": round(statistics.median(incr_split_times), 3),
            "incr_embed_secs_median": round(statistics.median(incr_embed_times), 3),
            "speedup": round(speedup, 2),
            "threshold_3x_met": "yes" if (ratio <= 0.15 and speedup >= 3.0) else "no",
        })

    # 写出 CSV
    print("\n" + "=" * 70)
    out_csv = BACKEND_ROOT / "tests" / "benchmark" / "results_S3.csv"
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    print(f"结果已写入: {out_csv.relative_to(BACKEND_ROOT)}")

    # 汇总
    print("\n汇总:")
    print(f"{'Ratio':>8} {'Files':>8} {'Full(s)':>10} {'Incr(s)':>10} {'Speedup':>10} {'Pass':>6}")
    for r in results:
        print(
            f"{r['change_ratio']:>7.0%} "
            f"{r['changed_files']:>8} "
            f"{r['full_total_secs_median']:>10.2f} "
            f"{r['incr_total_secs_median']:>10.2f} "
            f"{r['speedup']:>9.2f}x "
            f"{'✅' if r['threshold_3x_met'] == 'yes' else '—':>6}"
        )


if __name__ == "__main__":
    main()
