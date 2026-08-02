-- ============================================================
-- CodeNova 智码星 —— 数据库初始化脚本
-- 由 PostgreSQL 容器在首次启动时自动执行（docker-entrypoint-initdb.d）
-- ============================================================

-- 扩展
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- 用户表（阶段二鉴权使用，阶段一预留结构）
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id            BIGSERIAL PRIMARY KEY,
    username      VARCHAR(64)  NOT NULL UNIQUE,
    email         VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255),
    role          VARCHAR(32)  NOT NULL DEFAULT 'user',
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);
COMMENT ON TABLE users IS '系统用户';

-- ============================================================
-- 项目表：仓库解析记录
-- ============================================================
CREATE TABLE IF NOT EXISTS projects (
    id               BIGSERIAL PRIMARY KEY,
    user_id          BIGINT REFERENCES users(id) ON DELETE SET NULL,
    repo_url         TEXT         NOT NULL,
    repo_name        VARCHAR(255) NOT NULL,
    branch           VARCHAR(255),
    commit_sha       VARCHAR(64),
    language_stats   JSONB        NOT NULL DEFAULT '{}'::jsonb,
    status           VARCHAR(32)  NOT NULL DEFAULT 'pending',
    minio_object_key TEXT,
    error_message    TEXT,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);
COMMENT ON TABLE projects IS '仓库项目元数据';
CREATE INDEX IF NOT EXISTS idx_projects_user_id    ON projects(user_id);
CREATE INDEX IF NOT EXISTS idx_projects_status     ON projects(status);
CREATE INDEX IF NOT EXISTS idx_projects_repo_url   ON projects(repo_url);

-- ============================================================
-- 文档表：生成的各类文档
-- ============================================================
CREATE TABLE IF NOT EXISTS documents (
    id               BIGSERIAL PRIMARY KEY,
    project_id       BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    doc_type         VARCHAR(32)  NOT NULL,
    title            VARCHAR(255) NOT NULL,
    content          TEXT         NOT NULL DEFAULT '',
    minio_object_key TEXT,
    version          INTEGER      NOT NULL DEFAULT 1,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);
COMMENT ON TABLE documents IS '生成的文档（README/API/模块说明等）';
CREATE INDEX IF NOT EXISTS idx_documents_project_id ON documents(project_id);
CREATE INDEX IF NOT EXISTS idx_documents_doc_type   ON documents(doc_type);

-- ============================================================
-- 解析任务表：异步解析任务追踪
-- ============================================================
CREATE TABLE IF NOT EXISTS parsing_tasks (
    id            BIGSERIAL PRIMARY KEY,
    project_id    BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    celery_task_id VARCHAR(255),
    status        VARCHAR(32)  NOT NULL DEFAULT 'pending',
    total_files   INTEGER      NOT NULL DEFAULT 0,
    parsed_files  INTEGER      NOT NULL DEFAULT 0,
    total_symbols INTEGER      NOT NULL DEFAULT 0,
    progress      NUMERIC(5,2) NOT NULL DEFAULT 0.00,
    started_at    TIMESTAMPTZ,
    finished_at   TIMESTAMPTZ,
    error_message TEXT,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);
COMMENT ON TABLE parsing_tasks IS '代码解析异步任务状态';
CREATE INDEX IF NOT EXISTS idx_parsing_tasks_project_id ON parsing_tasks(project_id);
CREATE INDEX IF NOT EXISTS idx_parsing_tasks_status     ON parsing_tasks(status);

-- ============================================================
-- 代码块元数据表：与 Qdrant 向量索引互补，存储可检索的关系元数据
-- 实际向量在 Qdrant；此处存储符号定位、调用关系等结构化信息
-- ============================================================
CREATE TABLE IF NOT EXISTS code_chunks (
    id             BIGSERIAL PRIMARY KEY,
    project_id     BIGINT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    file_path      TEXT         NOT NULL,
    language       VARCHAR(32)  NOT NULL,
    symbol_name    VARCHAR(255),
    symbol_type    VARCHAR(32),
    qualified_name TEXT,
    start_line     INTEGER      NOT NULL,
    end_line       INTEGER      NOT NULL,
    qdrant_point_id VARCHAR(64),
    docstring      TEXT,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
);
COMMENT ON TABLE code_chunks IS '代码块结构化元数据（向量在 Qdrant）';
CREATE INDEX IF NOT EXISTS idx_code_chunks_project_id  ON code_chunks(project_id);
CREATE INDEX IF NOT EXISTS idx_code_chunks_symbol_name ON code_chunks(symbol_name);
CREATE INDEX IF NOT EXISTS idx_code_chunks_file_path   ON code_chunks(file_path);
CREATE INDEX IF NOT EXISTS idx_code_chunks_qdrant      ON code_chunks(qdrant_point_id);

-- ============================================================
-- 问答历史表
-- ============================================================
CREATE TABLE IF NOT EXISTS qa_history (
    id          BIGSERIAL PRIMARY KEY,
    project_id  BIGINT REFERENCES projects(id) ON DELETE CASCADE,
    question    TEXT        NOT NULL,
    answer      TEXT        NOT NULL,
    sources     JSONB       NOT NULL DEFAULT '[]'::jsonb,
    pinned      BOOLEAN     NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE qa_history IS '用户问答历史，pinned=true 表示已固化为文档';
CREATE INDEX IF NOT EXISTS idx_qa_history_project_id ON qa_history(project_id);

-- ============================================================
-- updated_at 触发器：自动维护更新时间
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE t TEXT;
BEGIN
    FOR t IN SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename IN ('users','projects') LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trg_%s_updated ON %s', t, t);
        EXECUTE format('CREATE TRIGGER trg_%s_updated BEFORE UPDATE ON %s FOR EACH ROW EXECUTE FUNCTION update_updated_at()', t, t);
    END LOOP;
END $$;
