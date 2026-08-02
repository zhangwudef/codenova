"""API Key 鉴权中间件单元测试。

不依赖外部服务，纯逻辑测试。
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import verify_api_key


@pytest.fixture
def secure_app(monkeypatch):
    """构造启用了 API Key 鉴权的最小应用。"""
    monkeypatch.setattr("app.core.security.settings.codenova_api_key", "test-secret-key-12345")

    app = FastAPI()
    from fastapi import Depends

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/v1/protected")
    async def protected(_: None = Depends(verify_api_key)):
        return {"data": "secret"}

    return app


@pytest.fixture
def open_app(monkeypatch):
    """构造未启用 API Key 鉴权的应用（开发模式）。"""
    monkeypatch.setattr("app.core.security.settings.codenova_api_key", "")

    app = FastAPI()
    from fastapi import Depends

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/v1/protected")
    async def protected(_: None = Depends(verify_api_key)):
        return {"data": "ok"}

    return app


class TestApiKeyAuth:
    """API Key 鉴权测试。"""

    def test_open_mode_no_key_required(self, open_app):
        """未配置 API Key 时，所有请求均可访问。"""
        client = TestClient(open_app)
        r = client.get("/api/v1/protected")
        assert r.status_code == 200
        assert r.json() == {"data": "ok"}

    def test_secure_mode_missing_key_returns_401(self, secure_app):
        """启用鉴权后，缺少 API Key 返回 401。"""
        client = TestClient(secure_app)
        r = client.get("/api/v1/protected")
        assert r.status_code == 401
        assert "Missing API key" in r.json()["detail"]

    def test_secure_mode_wrong_key_returns_401(self, secure_app):
        """错误的 API Key 返回 401。"""
        client = TestClient(secure_app)
        r = client.get("/api/v1/protected", headers={"X-API-Key": "wrong-key"})
        assert r.status_code == 401
        assert "Invalid API key" in r.json()["detail"]

    def test_secure_mode_correct_header_returns_200(self, secure_app):
        """正确的 X-API-Key 头通过鉴权。"""
        client = TestClient(secure_app)
        r = client.get(
            "/api/v1/protected", headers={"X-API-Key": "test-secret-key-12345"}
        )
        assert r.status_code == 200
        assert r.json() == {"data": "secret"}

    def test_secure_mode_query_param_passes(self, secure_app):
        """WebSocket 场景下，?api_key= 查询参数也应通过。"""
        client = TestClient(secure_app)
        r = client.get("/api/v1/protected?api_key=test-secret-key-12345")
        assert r.status_code == 200

    def test_health_endpoint_exempt(self, secure_app):
        """健康检查端点豁免鉴权。"""
        client = TestClient(secure_app)
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_docs_endpoint_exempt(self, secure_app):
        """OpenAPI 文档端点豁免鉴权。"""
        client = TestClient(secure_app)
        r = client.get("/docs")
        # /docs 返回 HTML，状态码 200
        assert r.status_code == 200

    def test_openapi_json_exempt(self, secure_app):
        """OpenAPI schema 端点豁免鉴权。"""
        client = TestClient(secure_app)
        r = client.get("/openapi.json")
        assert r.status_code == 200


class TestExemptPaths:
    """豁免路径逻辑测试。"""

    def test_health_is_exempt(self):
        from app.core.security import _is_exempt
        assert _is_exempt("/health") is True

    def test_health_subpath_is_exempt(self):
        from app.core.security import _is_exempt
        # /health 本身豁免；其下子路径也豁免（健康探针变体）
        assert _is_exempt("/health/ready") is True

    def test_docs_is_exempt(self):
        from app.core.security import _is_exempt
        assert _is_exempt("/docs") is True

    def test_api_path_not_exempt(self):
        from app.core.security import _is_exempt
        assert _is_exempt("/api/v1/repos/parse") is False

    def test_empty_path_not_exempt(self):
        from app.core.security import _is_exempt
        assert _is_exempt("/") is False
