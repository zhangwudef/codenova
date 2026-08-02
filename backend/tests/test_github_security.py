"""GitHub URL 安全校验单元测试。

覆盖 SSRF 防护与命令注入防护。
"""

from __future__ import annotations

import pytest

from app.services.github_service import GitHubService


class TestGithubUrlValidation:
    """GitHub URL 严格校验测试。"""

    @pytest.mark.parametrize(
        "url",
        [
            "https://github.com/pallets/flask",
            "https://github.com/pallets/flask.git",
            "https://github.com/pallets/flask/",
            "git@github.com:pallets/flask.git",
            "git@github.com:pallets/flask",
            "https://github.com/user-name/repo_name",
            "https://github.com/user.name/repo.name.git",
        ],
    )
    def test_valid_urls_pass(self, url):
        assert GitHubService._is_valid_github_url(url) is True

    @pytest.mark.parametrize(
        "url",
        [
            # SSRF: 子域名伪装
            "https://github.com.evil.com/pallets/flask",
            "https://evil-github.com/pallets/flask",
            "https://github.com.evil.com/",
            # 协议伪装
            "http://github.com/pallets/flask",
            "ftp://github.com/pallets/flask",
            "file:///etc/passwd",
            # 命令注入尝试
            "https://github.com/pallets/flask; rm -rf /",
            "https://github.com/pallets/flask$(whoami)",
            "https://github.com/pallets/flask`id`",
            "https://github.com/pallets/flask|cat /etc/passwd",
            # 路径越界
            "https://github.com/../etc/passwd",
            "https://github.com/pallets/flask/../../etc",
            # 空值与非法类型
            "",
            None,
            "not-a-url",
            "javascript:alert(1)",
            # 端口注入
            "https://github.com:6379/pallets/flask",
            # 凭证注入
            "https://user:pass@github.com/pallets/flask",
            # 路径中带查询参数
            "https://github.com/pallets/flask?ref=main",
        ],
    )
    def test_invalid_urls_rejected(self, url):
        assert GitHubService._is_valid_github_url(url) is False

    def test_validate_url_safe_raises_on_invalid(self):
        with pytest.raises(ValueError, match="非法的 GitHub 地址"):
            GitHubService._validate_url_safe("https://github.com.evil.com/x/y")

    def test_validate_url_safe_raises_on_ssr(self):
        with pytest.raises(ValueError):
            GitHubService._validate_url_safe("https://evil.com/x/y")

    def test_validate_url_safe_passes_on_valid(self):
        # 不抛异常即通过
        GitHubService._validate_url_safe("https://github.com/pallets/flask")
        GitHubService._validate_url_safe("git@github.com:pallets/flask.git")


class TestBranchValidation:
    """分支名校验测试。"""

    def test_valid_branch_names(self):
        # 不抛异常即通过（验证在 clone 方法中）
        # 这里直接测正则
        import re
        pattern = r"^[A-Za-z0-9._/\-]+$"
        assert re.match(pattern, "main")
        assert re.match(pattern, "feature/add-login")
        assert re.match(pattern, "release/v1.0.0")
        assert re.match(pattern, "bugfix/fix-123")

    def test_invalid_branch_names_rejected(self):
        import re
        pattern = r"^[A-Za-z0-9._/\-]+$"
        # 命令注入字符
        assert not re.match(pattern, "main; rm -rf /")
        assert not re.match(pattern, "main$(whoami)")
        assert not re.match(pattern, "main`id`")
        assert not re.match(pattern, "main|cat /etc/passwd")
        # 空格
        assert not re.match(pattern, "main feature")
