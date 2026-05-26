from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ResultError:
    code: str
    message: str
    retryable: bool = False
    detail: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class OperationResult:
    ok: bool
    operation: str
    target: Any
    capability: str
    adapter: dict[str, Any] | None
    data: Any = None
    warnings: tuple[str, ...] = ()
    error: ResultError | None = None
    raw_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "operation": self.operation,
            "target": self.target,
            "capability": self.capability,
            "adapter": self.adapter,
            "data": _serializable(self.data),
            "warnings": list(self.warnings),
            "error": self.error.to_dict() if self.error else None,
            "raw_ref": self.raw_ref,
        }


def _serializable(value: Any) -> Any:
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    if isinstance(value, dict):
        return {key: _serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serializable(item) for item in value]
    return value
