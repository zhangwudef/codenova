"""全局配置：基于 pydantic-settings 从环境变量加载。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """CodeNova 全局配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---------- 应用 ----------
    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    # 浏览器访问后端时使用的主机名（容器内为 0.0.0.0，浏览器需用 localhost 或对外域名）
    backend_external_host: str = "localhost"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"

    # ---------- 安全 ----------
    # API Key 鉴权：留空则不启用（仅本地开发）。生产环境务必设置强随机值。
    codenova_api_key: str = ""
    # CORS 允许的来源，逗号分隔。空列表时仅允许 localhost 开发域名。
    cors_allowed_origins: str = ""
    # Demo 模式：限制单次解析最大文件数，防止 OOM（生产环境建议设置）
    demo_max_files: int = 0  # 0 表示不限制

    # ---------- PostgreSQL ----------
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "codenova"
    # ⚠️ 生产环境必须修改：通过 .env 设置强密码
    postgres_password: str = "CHANGE_ME_IN_PRODUCTION"
    postgres_db: str = "codenova"
    postgres_dsn: str = ""

    @property
    def database_url(self) -> str:
        if self.postgres_dsn:
            return self.postgres_dsn
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # ---------- Redis / Celery ----------
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # ---------- Qdrant ----------
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection_code: str = "codenova_code_chunks"
    qdrant_collection_docs: str = "codenova_docs"
    qdrant_vector_size: int = 1024

    # ---------- MinIO ----------
    minio_host: str = "localhost"
    minio_port: int = 9000
    minio_root_user: str = "minioadmin"
    # ⚠️ 生产环境必须修改：通过 .env 设置强密码
    minio_root_password: str = "CHANGE_ME_IN_PRODUCTION"
    minio_secure: bool = False
    minio_bucket_repos: str = "codenova-repos"
    minio_bucket_docs: str = "codenova-docs"

    # ---------- GitHub ----------
    github_token: str = ""
    github_clone_base_dir: str = "/tmp/codenova_repos"

    # ---------- 代码解析 ----------
    supported_languages: tuple[str, ...] = (
        "python",
        "javascript",
        "typescript",
        "java",
        "go",
        "rust",
    )
    # 解析时跳过的目录
    ignore_dirs: tuple[str, ...] = (
        "node_modules",
        ".git",
        "__pycache__",
        ".venv",
        "venv",
        "dist",
        "build",
        ".idea",
        ".vscode",
        "target",
    )
    ignore_extensions: tuple[str, ...] = (".min.js", ".min.css", ".map", ".lock")
    max_file_size_kb: int = 512  # 超过此大小的文件跳过解析

    # ---------- LLM ----------
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    embedding_model: str = "BAAI/bge-m3"
    llm_model: str = "gpt-4o"

    @property
    def clone_base_path(self) -> Path:
        p = Path(self.github_clone_base_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def cors_origins(self) -> list[str]:
        """解析 CORS_ALLOWED_ORIGINS 环境变量，逗号分隔。"""
        if self.cors_allowed_origins:
            return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]
        # 开发环境默认
        return ["http://localhost:5173", "http://0.0.0.0:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
