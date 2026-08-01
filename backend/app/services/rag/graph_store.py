"""调用关系图索引服务（文档 4.1 节「双索引策略」）。

将 CallGraphExtractor 输出的 GraphData 持久化为 JSON 对象存入 MinIO，
按 repo_url 维度建立「调用关系图索引」。问答时可通过节点 ID 进行图遍历扩展，
实现「语义召回 + 图遍历溯源」的双索引策略。

存储路径：{minio_bucket_docs}/graph-index/{repo_key}.json
"""

from __future__ import annotations

import json
from collections import defaultdict

from loguru import logger

from app.core.config import settings
from app.services.analyzer.schemas import GraphData, GraphEdge, GraphNode
from app.services.minio_service import minio_service


def _repo_key(repo_url: str) -> str:
    """将 repo_url 转换为对象存储 key 用的稳定标识。"""
    if not repo_url:
        return "session"
    # 取最后一段并去除 .git 后缀
    key = repo_url.strip("/").split("/")[-1].replace(".git", "")
    # 简单 hash 防重名冲突
    return f"{key}_{abs(hash(repo_url)) % 100000:05d}"


class GraphStoreService:
    """调用关系图索引服务。

    - 持久化：save(graph_data)
    - 加载：load(repo_url)
    - 删除：delete(repo_url)
    - 邻居查询：neighbors(node_id, edge_type=None, direction='both')
    - 多跳扩展：expand(node_ids, max_depth=1)
    """

    def __init__(self) -> None:
        self._bucket = settings.minio_bucket_docs
        self._prefix = "graph-index"

    def _object_name(self, repo_url: str) -> str:
        return f"{self._prefix}/{_repo_key(repo_url)}.json"

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------
    def save(self, graph: GraphData) -> str:
        """保存图索引到 MinIO。返回 object_name。"""
        object_name = self._object_name(graph.repo_url)
        payload = {
            "repo_url": graph.repo_url,
            "nodes": [n.model_dump(mode="json") for n in graph.nodes],
            "edges": [e.model_dump(mode="json") for e in graph.edges],
            "elapsed_seconds": graph.elapsed_seconds,
            "saved_at": _now_iso(),
        }
        text = json.dumps(payload, ensure_ascii=False)
        try:
            minio_service.put_text(
                self._bucket,
                object_name,
                text,
                content_type="application/json; charset=utf-8",
            )
            logger.info(
                f"图索引保存成功: {object_name} "
                f"(nodes={len(graph.nodes)}, edges={len(graph.edges)})"
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"图索引保存失败: {e}")
        return object_name

    def load(self, repo_url: str) -> GraphData | None:
        """加载图索引。失败返回 None。"""
        if not repo_url:
            return None
        object_name = self._object_name(repo_url)
        try:
            text = minio_service.get_text(self._bucket, object_name)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"图索引加载失败 {object_name}: {e}")
            return None

        try:
            payload = json.loads(text)
            nodes = [GraphNode(**n) for n in payload.get("nodes", [])]
            edges = [GraphEdge(**e) for e in payload.get("edges", [])]
            return GraphData(
                nodes=nodes,
                edges=edges,
                repo_url=payload.get("repo_url", repo_url),
                elapsed_seconds=payload.get("elapsed_seconds", 0.0),
            )
        except Exception as e:  # noqa: BLE001
            logger.error(f"图索引解析失败 {object_name}: {e}")
            return None

    def delete(self, repo_url: str) -> bool:
        """删除图索引。"""
        if not repo_url:
            return False
        object_name = self._object_name(repo_url)
        try:
            minio_service.client.remove_object(self._bucket, object_name)
            logger.info(f"图索引已删除: {object_name}")
            return True
        except Exception as e:  # noqa: BLE001
            logger.debug(f"图索引删除失败 {object_name}: {e}")
            return False

    # ------------------------------------------------------------------
    # 图遍历查询
    # ------------------------------------------------------------------
    @staticmethod
    def build_adjacency(
        graph: GraphData,
    ) -> tuple[dict[str, list[GraphEdge]], dict[str, list[GraphEdge]]]:
        """构建邻接表：out_edges / in_edges。"""
        out_edges: dict[str, list[GraphEdge]] = defaultdict(list)
        in_edges: dict[str, list[GraphEdge]] = defaultdict(list)
        for edge in graph.edges:
            out_edges[edge.source].append(edge)
            in_edges[edge.target].append(edge)
        return out_edges, in_edges

    def neighbors(
        self,
        graph: GraphData,
        node_id: str,
        edge_types: set[str] | None = None,
        direction: str = "both",
    ) -> list[GraphNode]:
        """查询单节点的邻居节点。

        Args:
            graph: 图数据
            node_id: 起点节点 ID
            edge_types: 限定边类型（如 {"call"}），None 表示不限
            direction: both / out / in
        """
        node_map = {n.id: n for n in graph.nodes}
        out_edges, in_edges = self.build_adjacency(graph)

        result_ids: set[str] = set()
        if direction in ("both", "out"):
            for edge in out_edges.get(node_id, []):
                if edge_types and edge.type.value not in edge_types:
                    continue
                result_ids.add(edge.target)
        if direction in ("both", "in"):
            for edge in in_edges.get(node_id, []):
                if edge_types and edge.type.value not in edge_types:
                    continue
                result_ids.add(edge.source)

        return [node_map[nid] for nid in result_ids if nid in node_map]

    def expand(
        self,
        graph: GraphData,
        seed_node_ids: list[str],
        max_depth: int = 1,
        edge_types: set[str] | None = None,
    ) -> list[GraphNode]:
        """从种子节点出发做多跳 BFS 扩展。

        Args:
            graph: 图数据
            seed_node_ids: 种子节点 ID 列表
            max_depth: 最大跳数
            edge_types: 限定边类型

        Returns:
            扩展得到的节点列表（不含种子节点本身）
        """
        if not seed_node_ids or max_depth <= 0:
            return []

        node_map = {n.id: n for n in graph.nodes}
        visited: set[str] = set(seed_node_ids)
        result: list[GraphNode] = []
        frontier: list[str] = list(seed_node_ids)

        for _depth in range(max_depth):
            next_frontier: list[str] = []
            for nid in frontier:
                neighbors = self.neighbors(
                    graph, nid, edge_types=edge_types, direction="both"
                )
                for nb in neighbors:
                    if nb.id not in visited:
                        visited.add(nb.id)
                        result.append(nb)
                        next_frontier.append(nb.id)
            frontier = next_frontier
            if not frontier:
                break

        return result

    def find_nodes_by_qualified_name(
        self, graph: GraphData, qualified_names: list[str]
    ) -> list[GraphNode]:
        """按全限定名查找节点。"""
        target_set = set(qualified_names)
        return [n for n in graph.nodes if n.qualified_name in target_set]


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# 单例
graph_store_service = GraphStoreService()
