"""阶段一完成标准验证脚本。

验证内容：
1. PostgreSQL / Redis / Qdrant / MinIO 连通性与初始化状态
2. Tree-sitter 解析管线可稳定运行并输出预期结果
3. GitHub 仓库克隆能力（可选，需网络）

运行方式（容器内）：
    python -m scripts.verify_phase1
或：
    python backend/scripts/verify_phase1.py
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

from loguru import logger

CHECKS: list[tuple[str, bool]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, ok))
    mark = "✓" if ok else "✗"
    msg = f"  {mark} {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)


# ------------------------------------------------------------------
def check_postgres() -> None:
    print("\n[1/5] PostgreSQL 连通性")
    try:
        from sqlalchemy import text

        from app.core.database import SessionLocal

        with SessionLocal() as db:
            res = db.execute(text("SELECT 1 AS one")).scalar()
            assert res == 1
        # 验证 init_db.sql 建表
        from app.core.database import engine

        with engine.connect() as conn:
            tables = conn.execute(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname='public' "
                    "ORDER BY tablename"
                )
            ).scalars().all()
        expected = {"users", "projects", "documents", "parsing_tasks", "code_chunks", "qa_history"}
        missing = expected - set(tables)
        record("SELECT 1 连通", True)
        record("init_db.sql 建表完整", not missing, f"表={tables}" if not missing else f"缺失={missing}")
    except Exception as e:  # noqa: BLE001
        record("PostgreSQL", False, str(e))


def check_redis() -> None:
    print("\n[2/5] Redis 连通性")
    try:
        import redis as _redis

        from app.core.config import settings

        r = _redis.Redis(
            host=settings.redis_host, port=settings.redis_port,
            password=settings.redis_password or None, db=settings.redis_db,
            socket_connect_timeout=3,
        )
        assert r.ping() is True
        record("PING", True)
    except Exception as e:  # noqa: BLE001
        record("Redis", False, str(e))


def check_qdrant() -> None:
    print("\n[3/5] Qdrant 连通性与集合初始化")
    try:
        from app.services.qdrant_service import qdrant_service

        qdrant_service.init_all()
        collections = qdrant_service.list_collections()
        record("集合初始化", True, f"collections={collections}")
    except Exception as e:  # noqa: BLE001
        record("Qdrant", False, str(e))


def check_minio() -> None:
    print("\n[4/5] MinIO 连通性与桶初始化")
    try:
        from app.services.minio_service import minio_service

        minio_service.init_all()
        buckets = minio_service.list_buckets()
        record("桶初始化", True, f"buckets={buckets}")
    except Exception as e:  # noqa: BLE001
        record("MinIO", False, str(e))


def check_parsing_pipeline() -> None:
    print("\n[5/5] 代码解析管线（自解析 backend 源码）")
    try:
        from app.services.parser.pipeline import ParsingPipeline

        # 找到 backend 源码目录进行自解析
        backend_root = Path(__file__).resolve().parent.parent
        # 临时复制一份样本到独立目录解析（避免 __pycache__ 干扰）
        with tempfile.TemporaryDirectory() as tmp:
            sample = Path(tmp) / "sample.py"
            sample.write_text(
                '"""样本模块。"""\n'
                "def hello(name: str) -> str:\n"
                '    """打招呼。"""\n'
                '    return f"hi {name}"\n\n'
                "class Service:\n"
                "    def run(self):\n"
                "        return hello('world')\n",
                encoding="utf-8",
            )
            pipeline = ParsingPipeline()
            summary = pipeline.run(tmp, repo_url="local://sample", max_files=50)

        assert summary.parsed_files >= 1, "应至少解析 1 个文件"
        assert summary.total_symbols >= 3, f"应至少识别 3 个符号，实际 {summary.total_symbols}"
        # 验证符号类型分布
        sym_types = {c.symbol_type.value for c in summary.sample_chunks}
        record("管线执行", True, f"文件={summary.parsed_files} 符号={summary.total_symbols} 耗时={summary.elapsed_seconds:.3f}s")
        record("AST 切分产出代码块", summary.total_chunks >= 3, f"chunks={summary.total_chunks}")
        record("符号元数据完整", bool(sym_types), f"types={sym_types}")
    except Exception as e:  # noqa: BLE001
        record("解析管线", False, str(e))


def check_github_clone() -> None:
    """可选检查：GitHub 克隆能力（需网络，失败不阻断阶段一判定）。"""
    print("\n[可选] GitHub 仓库克隆")
    try:
        from app.services.github_service import github_service

        # 用一个极小仓库验证
        path = github_service.clone("https://github.com/octocat/Hello-World.git", branch="master")
        files = list(path.rglob("*"))
        github_service.cleanup(path)
        record("git clone 公开仓库", len(files) > 0, f"clone 后文件数={len(files)}")
    except Exception as e:  # noqa: BLE001
        record("GitHub 克隆（可选）", False, f"需网络/Token: {e}")


def main() -> int:
    print("=" * 60)
    print("CodeNova 阶段一完成标准验证")
    print("=" * 60)

    check_postgres()
    check_redis()
    check_qdrant()
    check_minio()
    check_parsing_pipeline()
    check_github_clone()

    print("\n" + "=" * 60)
    total = len(CHECKS)
    passed = sum(1 for _, ok in CHECKS if ok)
    print(f"结果: {passed}/{total} 通过")
    failed = [n for n, ok in CHECKS if not ok]
    if failed:
        print("失败项:")
        for n in failed:
            print(f"  - {n}")
    print("=" * 60)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
