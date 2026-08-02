"""项目与文档元数据 ORM 模型。

对应 init_db.sql 中的表结构，阶段二用于 CRUD；阶段一仅建立映射。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Project(Base):
    """代码仓库项目。"""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    repo_url: Mapped[str] = mapped_column(Text, nullable=False)
    repo_name: Mapped[str] = mapped_column(String(255), nullable=False)
    branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    language_stats: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    minio_object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    documents: Mapped[list[Document]] = relationship(back_populates="project", cascade="all, delete-orphan")
    parsing_tasks: Mapped[list[ParsingTask]] = relationship(back_populates="project", cascade="all, delete-orphan")
    code_chunks: Mapped[list[CodeChunkMeta]] = relationship(back_populates="project", cascade="all, delete-orphan")


class Document(Base):
    """生成的文档。"""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    minio_object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped[Project] = relationship(back_populates="documents")


class ParsingTask(Base):
    """解析任务追踪。"""

    __tablename__ = "parsing_tasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    total_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parsed_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_symbols: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress: Mapped[float] = mapped_column(nullable=False, default=0.0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped[Project] = relationship(back_populates="parsing_tasks")


class CodeChunkMeta(Base):
    """代码块元数据（向量在 Qdrant）。"""

    __tablename__ = "code_chunks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(32), nullable=False)
    symbol_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    symbol_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    qualified_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    qdrant_point_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    docstring: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project: Mapped[Project] = relationship(back_populates="code_chunks")