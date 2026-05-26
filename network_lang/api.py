from __future__ import annotations

import re
from typing import Any

from .model import Operation

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


class OperationBuilder:
    """Build operations with attribute access that mirrors UNS names."""

    __slots__ = ("_namespace", "_segments")

    def __init__(self, namespace: str = "network", segments: tuple[str, ...] = ()) -> None:
        self._namespace = namespace
        self._segments = segments

    def __getattr__(self, segment: str) -> "OperationBuilder":
        if not _valid_identifier(segment):
            raise AttributeError(segment)
        return OperationBuilder(self._namespace, (*self._segments, segment))

    def __call__(self, **params: Any) -> Operation:
        if len(self._segments) < 2:
            raise ValueError(
                "operation must include at least one resource segment and an action"
            )
        return Operation(
            namespace=self._namespace,
            resource_path=self._segments[:-1],
            action=self._segments[-1],
            params=dict(params),
        )

    def __repr__(self) -> str:
        path = ".".join((self._namespace, *self._segments))
        return f"{type(self).__name__}({path})"


network = OperationBuilder()


def build_operation(operation_name: str, **params: Any) -> Operation:
    """Build an operation from a dotted operation name.

    Args:
        operation_name:
        **params:
    """

    parts = tuple(operation_name.split("."))
    if len(parts) < 3:
        raise ValueError("operation name must look like namespace.resource.action")
    for part in parts:
        if not _valid_identifier(part):
            raise ValueError(f"invalid operation name segment: {part!r}")

    return Operation(
        namespace=parts[0],
        resource_path=parts[1:-1],
        action=parts[-1],
        params=dict(params),
    )


def _valid_identifier(value: str) -> bool:
    return bool(_IDENTIFIER.fullmatch(value))
