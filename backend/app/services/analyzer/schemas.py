"""依赖图与时序图数据模型。"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    """依赖图节点类型（对应文档 3.2 节）。"""

    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    INTERFACE = "interface"


class EdgeType(str, Enum):
    """依赖图边类型（对应文档 3.2 节）。"""

    IMPORT = "import"
    CALL = "call"
    INHERIT = "inherit"
    IMPLEMENT = "implement"


class GraphNode(BaseModel):
    """依赖图节点。"""

    id: str = Field(..., description="节点唯一 ID（类型:文件路径:全限定名）")
    type: NodeType
    label: str = Field(..., description="显示名称")
    file_path: str
    qualified_name: str | None = Field(default=None, description="全限定名")
    start_line: int | None = None
    end_line: int | None = None


class GraphEdge(BaseModel):
    """依赖图边。"""

    id: str
    source: str = Field(..., description="起点节点 ID")
    target: str = Field(..., description="终点节点 ID")
    type: EdgeType


class GraphData(BaseModel):
    """完整依赖图。"""

    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    repo_url: str = ""
    elapsed_seconds: float = 0.0


class SequenceParticipant(BaseModel):
    """时序图参与者。"""

    id: str
    name: str
    type: str = Field(default="participant", description="actor/participant")


class SequenceMessage(BaseModel):
    """时序图消息。"""

    id: str
    from_participant: str = Field(..., alias="from")
    to_participant: str = Field(..., alias="to")
    label: str = ""
    kind: str = Field(default="message", description="message/return/note")


class SequenceData(BaseModel):
    """时序图数据（供前端 Mermaid 渲染）。"""

    title: str = ""
    participants: list[SequenceParticipant] = Field(default_factory=list)
    messages: list[SequenceMessage] = Field(default_factory=list)
    mermaid_syntax: str = Field(default="", description="可直接渲染的 Mermaid sequenceDiagram 语法")
    repo_url: str = ""
    entry_function: str = ""
    elapsed_seconds: float = 0.0

    model_config = {"populate_by_name": True}
