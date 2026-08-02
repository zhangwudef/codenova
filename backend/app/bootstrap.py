"""启动初始化脚本。

在容器启动时由 docker-compose 调用，确保：
1. Qdrant 集合存在
2. MinIO 存储桶存在
3. Tree-sitter 语言解析器已预热

对应阶段一「配置并初始化 Qdrant/MinIO 服务」与「验证数据服务连通性」。
"""

from __future__ import annotations

import sys

from loguru import logger


def main() -> int:
    logger.info("====== CodeNova 启动初始化开始 ======")

    exit_code = 0

    # 1. Tree-sitter 语言预热
    try:
        from app.services.parser.languages import LanguageRegistry

        LanguageRegistry.build_all()
        logger.info("[1/3] Tree-sitter 语言预热 ✓")
    except Exception as e:  # noqa: BLE001
        logger.error(f"[1/3] Tree-sitter 预热失败: {e}")
        exit_code = 1

    # 2. Qdrant 集合初始化
    try:
        from app.services.qdrant_service import qdrant_service

        qdrant_service.init_all()
        logger.info("[2/3] Qdrant 集合初始化 ✓")
    except Exception as e:  # noqa: BLE001
        logger.error(f"[2/3] Qdrant 初始化失败: {e}")
        exit_code = 1

    # 3. MinIO 存储桶初始化
    try:
        from app.services.minio_service import minio_service

        minio_service.init_all()
        logger.info("[3/3] MinIO 存储桶初始化 ✓")
    except Exception as e:  # noqa: BLE001
        logger.error(f"[3/3] MinIO 初始化失败: {e}")
        exit_code = 1

    if exit_code == 0:
        logger.info("====== 启动初始化完成 ======")
    else:
        logger.warning("====== 启动初始化部分失败，服务仍将启动（外部依赖可能未就绪） ======")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
