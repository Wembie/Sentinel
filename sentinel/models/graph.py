from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class NodeType(str, Enum):
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


class EdgeType(str, Enum):
    CALLS = "calls"
    IMPORTS = "imports"
    INHERITS = "inherits"
    DATA_FLOW = "data_flow"
    TRUST_BOUNDARY = "trust_boundary"
    HTTP_REQUEST = "http_request"
    DB_QUERY = "db_query"
    READS_SECRET = "reads_secret"
    WRITES_OUTPUT = "writes_output"


class TrustLevel(str, Enum):
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
