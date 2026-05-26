from __future__ import annotations

from dataclasses import dataclass
from typing import Any


CORE_ACTIONS = frozenset(
    {
        "list",
        "get",
        "create",
        "update",
        "delete",
        "enable",
        "disable",
        "observe",
        "run",
        "backup",
        "diff",
        "validate",
    }
)

RISK_BY_ACTION = {
    "list": "read",
    "get": "read",
    "backup": "read",
    "diff": "read",
    "validate": "read",
    "observe": "observe",
    "run": "observe",
    "create": "write",
    "update": "write",
    "enable": "write",
    "delete": "destructive",
    "disable": "destructive",
}


@dataclass(frozen=True)
class SourceSpan:
    path: str | None
    line: int
    column: int = 1

    def label(self) -> str:
        if self.path:
            return f"{self.path}:{self.line}:{self.column}"
        return f"<input>:{self.line}:{self.column}"


@dataclass(frozen=True)
class Operation:
    namespace: str
    resource_path: tuple[str, ...]
    action: str
    params: dict[str, Any]
    source: SourceSpan | None = None

    @property
    def name(self) -> str:
        path = ".".join((self.namespace, *self.resource_path, self.action))
        return path

    @property
    def target(self) -> Any:
        return self.params.get("target")

    @property
    def risk(self) -> str:
        return RISK_BY_ACTION.get(self.action, "unknown")

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "namespace": self.namespace,
            "resource_path": list(self.resource_path),
            "action": self.action,
            "risk": self.risk,
            "target": self.target,
            "params": self.params,
            "source": {
                "path": self.source.path,
                "line": self.source.line,
                "column": self.source.column,
            }
            if self.source
            else None,
        }

