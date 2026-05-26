from __future__ import annotations

from dataclasses import dataclass

from .model import CORE_ACTIONS, Operation


@dataclass(frozen=True)
class Diagnostic:
    level: str
    message: str
    operation: Operation | None = None

    @property
    def is_error(self) -> bool:
        return self.level == "error"

    def label(self) -> str:
        if self.operation and self.operation.source:
            return self.operation.source.label()
        return "<input>:1:1"


def validate_operations(operations: list[Operation]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for operation in operations:
        diagnostics.extend(validate_operation(operation))
    return diagnostics


def validate_operation(operation: Operation) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []

    if operation.namespace != "network":
        diagnostics.append(
            Diagnostic("error", "operation must use the 'network' namespace", operation)
        )

    if not operation.resource_path:
        diagnostics.append(
            Diagnostic("error", "operation must include a resource path", operation)
        )

    if operation.action not in CORE_ACTIONS:
        actions = ", ".join(sorted(CORE_ACTIONS))
        diagnostics.append(
            Diagnostic(
                "error",
                f"unknown action '{operation.action}' (expected one of: {actions})",
                operation,
            )
        )

    if "target" not in operation.params:
        diagnostics.append(
            Diagnostic("error", "operation must include target=...", operation)
        )
    elif not isinstance(operation.target, str) or not operation.target.strip():
        diagnostics.append(
            Diagnostic("error", "target must be a non-empty string", operation)
        )

    return diagnostics

