"""配置加载测试，覆盖 CORS 与安全配置。"""

from __future__ import annotations

import pytest

from app.core.config import Settings


class TestCorsConfig:
    """CORS 配置测试。"""

    def test_default_cors_origins_for_dev(self, monkeypatch):
        """未配置 CORS_ALLOWED_ORIGINS 时回退到开发默认值。"""
        monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
        s = Settings(_env_file=None)
        assert "http://localhost:5173" in s.cors_origins
        assert "http://0.0.0.0:5173" in s.cors_origins

    def test_single_origin(self, monkeypatch):
        monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://example.com")
        s = Settings(_env_file=None)
        assert s.cors_origins == ["https://example.com"]

    def test_multiple_origins_comma_separated(self, monkeypatch):
        monkeypatch.setenv(
            "CORS_ALLOWED_ORIGINS",
            "https://a.com, https://b.com,https://c.com",
        )
        s = Settings(_env_file=None)
        assert s.cors_origins == ["https://a.com", "https://b.com", "https://c.com"]

    def test_empty_origins_filtered(self, monkeypatch):
        monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://a.com,,  ,https://b.com")
        s = Settings(_env_file=None)
        assert s.cors_origins == ["https://a.com", "https://b.com"]


class TestSecurityConfig:
    """安全相关配置测试。"""

    def test_api_key_default_empty(self):
        s = Settings(_env_file=None)
        assert s.codenova_api_key == ""

    def test_demo_max_files_default_zero(self):
        s = Settings(_env_file=None)
        assert s.demo_max_files == 0

    def test_demo_max_files_from_env(self, monkeypatch):
        monkeypatch.setenv("DEMO_MAX_FILES", "150")
        s = Settings(_env_file=None)
        assert s.demo_max_files == 150


class TestDefaultPasswords:
    """默认密码应为占位符，而非真实密码。"""

    def test_postgres_password_is_placeholder(self):
        s = Settings(_env_file=None)
        assert "CHANGE_ME" in s.postgres_password
        # 不应包含历史硬编码值
        assert s.postgres_password != "codenova_dev_2026"

    def test_minio_password_is_placeholder(self):
        s = Settings(_env_file=None)
        assert "CHANGE_ME" in s.minio_root_password
        # 不应包含历史硬编码值
        assert s.minio_root_password != "minioadmin123"
