"""GitHub 仓库拉取服务。

使用 git clone 拉取公开仓库至本地临时目录。
阶段二将补充：归档至 MinIO、记录 commit 历史、支持私有仓库 Token 鉴权。
增量更新支持：获取 HEAD commit、比对两次 commit 之间的变更文件（文档 4.1 节）。
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from urllib.parse import urlparse

from loguru import logger

from app.core.config import settings


# 严格的 GitHub URL 模式：仅允许 github.com 主机名，禁止子域名伪装
_GITHUB_HTTPS_PATTERN = re.compile(
    r"^https://github\.com/[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+(?:\.git)?/?$"
)
_GITHUB_SSH_PATTERN = re.compile(
    r"^git@github\.com:[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+(?:\.git)?$"
)

# 允许的协议与主机
_ALLOWED_HOSTS = {"github.com"}


class GitHubService:
    """GitHub 仓库克隆服务。"""

    def __init__(self) -> None:
        self.base_dir: Path = settings.clone_base_path

    @staticmethod
    def _is_valid_github_url(url: str) -> bool:
        """严格校验 GitHub URL。

        防御点:
        - 仅允许 github.com 主机名（防止 https://github.com.evil.com/ 伪装）
        - 仅允许 https 与 ssh 协议
        - 仓库路径字符白名单（防止命令注入）
        """
        if not url or not isinstance(url, str):
            return False
        if _GITHUB_HTTPS_PATTERN.match(url):
            return True
        if _GITHUB_SSH_PATTERN.match(url):
            return True
        return False

    @staticmethod
    def _validate_url_safe(url: str) -> None:
        """对 URL 做安全校验，不通过则抛 ValueError。"""
        if not GitHubService._is_valid_github_url(url):
            raise ValueError(
                f"非法的 GitHub 地址: {url!r}. 仅允许 https://github.com/<owner>/<repo> 或 git@github.com:<owner>/<repo> 格式。"
            )
        # 二次解析校验：确认主机名确为 github.com
        try:
            if url.startswith("https://"):
                parsed = urlparse(url)
                if parsed.hostname not in _ALLOWED_HOSTS:
                    raise ValueError(f"非允许的主机名: {parsed.hostname}")
            # SSH 格式不通过 urlparse 解析，已在正则阶段严格校验
        except Exception as e:
            raise ValueError(f"URL 解析失败: {e}") from e

    def clone(self, repo_url: str, branch: str | None = None) -> Path:
        """克隆仓库到本地，返回目标目录。

        Args:
            repo_url: GitHub 仓库 HTTPS / SSH 地址
            branch: 指定分支；None 表示默认分支

        Raises:
            ValueError: URL 非法
            RuntimeError: git clone 失败
        """
        # 严格校验 URL，防止 SSRF 与命令注入
        self._validate_url_safe(repo_url)

        # branch 校验：仅允许字母数字 / . _ - /
        if branch and not re.match(r"^[A-Za-z0-9._/\-]+$", branch):
            raise ValueError(f"非法的分支名: {branch!r}")

        # 以短 UUID 命名避免冲突
        target = self.base_dir / f"repo_{uuid.uuid4().hex[:10]}"
        cmd = ["git", "clone", "--depth", "1"]
        if branch:
            cmd += ["--branch", branch]
        cmd += [repo_url, str(target)]

        logger.info(f"执行克隆: {' '.join(cmd)}")
        env = os.environ.copy()
        if settings.github_token and repo_url.startswith("https://"):
            # 注入 token 用于私有仓库（阶段一主要为公开仓库，留空即可）
            repo_url_authed = repo_url.replace(
                "https://",
                f"https://x-access-token:{settings.github_token}@",
            )
            cmd[cmd.index(repo_url)] = repo_url_authed

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300, env=env, check=False
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise RuntimeError(f"git clone 失败: {stderr}")

        logger.info(f"克隆完成 → {target}")
        return target

    @staticmethod
    def cleanup(path: Path) -> None:
        """删除本地克隆目录。"""
        if path and path.exists():
            shutil.rmtree(path, ignore_errors=True)
            logger.debug(f"已清理临时目录: {path}")

    # ------------------------------------------------------------------
    # 增量更新支持（文档 4.1 节「增量文档更新」）
    # ------------------------------------------------------------------
    @staticmethod
    def get_head_commit(repo_path: Path) -> str | None:
        """获取仓库当前 HEAD commit hash。失败返回 None。"""
        try:
            result = subprocess.run(
                ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=10, check=False,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:  # noqa: BLE001
            logger.debug(f"获取 HEAD commit 失败: {e}")
        return None

    @staticmethod
    def list_changed_files(
        repo_path: Path, old_commit: str, new_commit: str = "HEAD"
    ) -> dict[str, list[str]]:
        """比对两次 commit 之间的变更文件。

        Returns:
            {"added": [...], "modified": [...], "deleted": [...], "renamed": [...]}
        """
        result: dict[str, list[str]] = {
            "added": [], "modified": [], "deleted": [], "renamed": [],
        }
        try:
            cmd = [
                "git", "-C", str(repo_path), "diff", "--name-status",
                old_commit, new_commit,
            ]
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30, check=False
            )
            if proc.returncode != 0:
                logger.warning(f"git diff 失败: {proc.stderr.strip()}")
                return result

            for line in proc.stdout.splitlines():
                if not line.strip():
                    continue
                parts = line.split("\t")
                status = parts[0]
                # 状态码可能带分数（如 R100 表示重命名相似度 100）
                code = status[0].upper()
                if code == "A":
                    result["added"].append(parts[1])
                elif code == "M":
                    result["modified"].append(parts[1])
                elif code == "D":
                    result["deleted"].append(parts[1])
                elif code == "R" and len(parts) >= 3:
                    result["renamed"].append(parts[2])
                elif code == "C" and len(parts) >= 3:
                    result["added"].append(parts[2])
        except Exception as e:  # noqa: BLE001
            logger.warning(f"列出变更文件失败: {e}")
        return result


github_service = GitHubService()
