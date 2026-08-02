"""MinIO 对象存储服务封装。

职责：
- 初始化仓库源码 / 生成文档两个存储桶
- 提供桶列表查询（用于连通性检查）
- 文档对象的上传 / 预签名下载（文档 4.2 节「问答即文档」）
"""

from __future__ import annotations

import io
from datetime import timedelta

from loguru import logger
from minio import Minio

from app.core.config import settings


class MinioService:
    """MinIO 客户端单例封装。"""

    def __init__(self) -> None:
        self._client: Minio | None = None

    @property
    def client(self) -> Minio:
        if self._client is None:
            self._client = Minio(
                endpoint=f"{settings.minio_host}:{settings.minio_port}",
                access_key=settings.minio_root_user,
                secret_key=settings.minio_root_password,
                secure=settings.minio_secure,
            )
        return self._client

    def ensure_bucket(self, name: str) -> bool:
        """确保桶存在；若不存在则创建。返回是否新建。"""
        exists = self.client.bucket_exists(name)
        if not exists:
            self.client.make_bucket(name)
            logger.info(f"创建 MinIO 桶: {name}")
            return True
        return False

    def init_all(self) -> None:
        """初始化所有业务桶。"""
        self.ensure_bucket(settings.minio_bucket_repos)
        self.ensure_bucket(settings.minio_bucket_docs)
        logger.info("MinIO 存储桶初始化完成")

    def list_buckets(self) -> list[str]:
        return [b.name for b in self.client.list_buckets()]

    def ping(self) -> bool:
        try:
            self.client.list_buckets()
            return True
        except Exception:  # noqa: BLE001
            return False

    def put_text(
        self,
        bucket: str,
        object_name: str,
        text: str,
        content_type: str = "text/markdown; charset=utf-8",
    ) -> str:
        """上传文本内容到指定桶，返回对象名。

        Args:
            bucket: 桶名
            object_name: 对象名（含路径）
            text: 文本内容
            content_type: MIME 类型

        Returns:
            object_name
        """
        self.ensure_bucket(bucket)
        data = text.encode("utf-8")
        stream = io.BytesIO(data)
        self.client.put_object(
            bucket_name=bucket,
            object_name=object_name,
            data=stream,
            length=len(data),
            content_type=content_type,
        )
        logger.info(f"MinIO 上传成功: {bucket}/{object_name} ({len(data)} bytes)")
        return object_name

    def presigned_get(
        self,
        bucket: str,
        object_name: str,
        expires: timedelta = timedelta(hours=1),
    ) -> str:
        """生成预签名下载 URL。"""
        return self.client.presigned_get_object(bucket, object_name, expires=expires)

    def get_text(self, bucket: str, object_name: str) -> str:
        """获取文本对象内容。"""
        resp = self.client.get_object(bucket, object_name)
        try:
            return resp.read().decode("utf-8")
        finally:
            resp.close()
            resp.release_conn()


minio_service = MinioService()
