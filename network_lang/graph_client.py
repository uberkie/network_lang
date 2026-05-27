from __future__ import annotations

from datetime import datetime, timezone
import time as clock
from typing import Any, Iterable, Mapping, Sequence

from .graphing import BarGraph, Field, LineGraph, bar_graph, line_graph


def graph_operation(
    device: Any,
    operation_name: str,
    *,
    y: Field | Sequence[Field],
    x: Field | None = None,
    group_by: Field | Sequence[Field] | None = None,
    kind: str = "auto",
    title: str | None = None,
    samples: int = 1,
    interval: float = 5.0,
    match: Mapping[str, Any] | None = None,
    params: Mapping[str, Any] | None = None,
    aggregate: str | None = None,
    count: bool = False,
    rate: bool | None = None,
) -> LineGraph | BarGraph:
    """Execute an operation and build a graph from adapter-normalized records."""
    if samples < 1:
        raise ValueError("samples must be at least 1")

    if kind == "auto":
        graph_kind = "line" if samples > 1 else "bar"
    else:
        graph_kind = kind
    if graph_kind not in {"line", "bar"}:
        raise ValueError(f"unsupported graph kind: {kind!r}")

    resolved_group = group_by or _adapter_default_graph_group_by(device, operation_name)
    records = _collect_operation_records(
        device,
        operation_name,
        samples=samples,
        interval=interval,
        match=match,
        params=params,
    )

    if graph_kind == "line":
        x_field = x or "timestamp"
        records, graph_y = _adapter_prepare_graph_records(
            device,
            records,
            y=y,
            x=x_field,
            group_by=resolved_group,
            samples=samples,
            kind=graph_kind,
            rate=rate,
        )
        return line_graph(
            records,
            x=x_field,
            y=graph_y,
            group_by=resolved_group,
            title=title or _graph_title(graph_y, resolved_group or x_field),
        )

    fields = _graph_fields(y)
    x_field = x or resolved_group or (fields[0] if fields else "value")
    y_field = None if count else (fields[0] if fields else None)
    return bar_graph(
        records,
        x=x_field,
        y=y_field,
        group_by=None if x_field == resolved_group else resolved_group,
        title=title or _graph_title(y_field or "count", x_field),
        aggregate=aggregate or ("count" if y_field is None else "latest"),
    )


def _collect_operation_records(
    device: Any,
    operation_name: str,
    *,
    samples: int,
    interval: float,
    match: Mapping[str, Any] | None,
    params: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], ...]:
    operation_params = dict(params or {})
    if match:
        operation_params["match"] = dict(match)

    rows: list[dict[str, Any]] = []
    for sample in range(samples):
        operation = device.operation(operation_name, **operation_params)
        result = device.execute(operation)
        if not result.ok:
            message = result.error.message if result.error else "operation failed"
            raise RuntimeError(message)

        sampled_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        for row in _result_rows(result.data):
            rows.append(
                {
                    **row,
                    "timestamp": sampled_at,
                    "sample": sample,
                    "operation": operation_name,
                    "target": getattr(device, "name", result.target),
                }
            )

        if sample + 1 < samples:
            clock.sleep(interval)

    return tuple(rows)


def _result_rows(data: Any) -> tuple[dict[str, Any], ...]:
    if isinstance(data, Mapping):
        return (dict(data),)
    if isinstance(data, (str, bytes)) or data is None:
        return ()
    try:
        return tuple(dict(row) for row in data if isinstance(row, Mapping))
    except TypeError:
        return ()


def _adapter_default_graph_group_by(device: Any, operation_name: str) -> str | None:
    vendor = str(getattr(device, "vendor", "")).lower()
    platform = str(getattr(device, "platform", "")).lower()
    if vendor in {"mikrotik", "routeros"} or platform == "routeros":
        from .adapters import routeros_default_graph_group_by

        return routeros_default_graph_group_by(operation_name)
    return None


def _adapter_prepare_graph_records(
    device: Any,
    records: Iterable[dict[str, Any]],
    *,
    y: Field | Sequence[Field],
    x: Field,
    group_by: Field | Sequence[Field] | None,
    samples: int,
    kind: str,
    rate: bool | None,
) -> tuple[tuple[dict[str, Any], ...], Field | Sequence[Field]]:
    vendor = str(getattr(device, "vendor", "")).lower()
    platform = str(getattr(device, "platform", "")).lower()
    if vendor in {"mikrotik", "routeros"} or platform == "routeros":
        from .adapters import routeros_prepare_graph_records

        return routeros_prepare_graph_records(
            records,
            y=y,
            x=_field_name(x),
            group_by=group_by,
            samples=samples,
            kind=kind,
            rate=rate,
        )
    return tuple(records), _graph_field_value(list(_graph_fields(y)))


def _graph_fields(value: Field | Sequence[Field] | None) -> tuple[Field, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        fields = tuple(part.strip() for part in value.split(",") if part.strip())
        return fields or (value,)
    if callable(value):
        return (value,)
    return tuple(value)


def _graph_field_value(fields: list[Field]) -> Field | Sequence[Field]:
    if len(fields) == 1:
        return fields[0]
    return tuple(fields)


def _graph_title(y: Field | Sequence[Field] | None, x: Field | Sequence[Field]) -> str:
    y_label = _field_display(_graph_fields(y)) if y is not None else "count"
    x_label = _field_display(_graph_fields(x))
    return f"{_title_text(y_label)} by {_title_text(x_label)}"


def _field_name(field: Field | None) -> str:
    if field is None:
        return "value"
    if isinstance(field, str):
        return field
    return getattr(field, "__name__", "value")


def _field_display(fields: Sequence[Field]) -> str:
    return ", ".join(_field_name(field) for field in fields)


def _title_text(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").replace(",", ", ").title()
