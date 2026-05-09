from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class NodeType(StrEnum):
    FILE = "file"
    FUNCTION = "function"
    CLASS = "class"
    MODULE = "module"
    ENDPOINT = "endpoint"
    DATABASE = "database"
    QUEUE = "queue"
    SERVICE = "service"
    SECRET = "secret"
    CONFIG = "config"
    USER_INPUT = "user_input"
    OUTPUT = "output"


class EdgeType(StrEnum):
    CALLS = "calls"
    IMPORTS = "imports"
    INHERITS = "inherits"
    DATA_FLOW = "data_flow"
    TRUST_BOUNDARY = "trust_boundary"
    HTTP_REQUEST = "http_request"
    DB_QUERY = "db_query"
    READS_SECRET = "reads_secret"
    WRITES_OUTPUT = "writes_output"


class TrustLevel(StrEnum):
    UNTRUSTED = "untrusted"
    SEMI_TRUSTED = "semi_trusted"
    TRUSTED = "trusted"
    PRIVILEGED = "privileged"


class GraphNode(BaseModel):
    id: str
    type: NodeType
    label: str
    trust_level: TrustLevel = TrustLevel.SEMI_TRUSTED
    file: str | None = None
    line: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    type: EdgeType
    label: str | None = None
    tainted: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
