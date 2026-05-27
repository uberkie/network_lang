from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
import math
from typing import Any, Callable, Iterable, Mapping, Sequence

from .result import OperationResult

Field = str | Callable[[Any], Any]
FieldAliases = Mapping[str, Sequence[str]]
DerivedFields = Mapping[str, Callable[[Any], Any]]
RecordFilter = Callable[[Any], bool]

_FIELD_ALIASES = {
    "interface": ("name", "default_name"),
    "timestamp": ("sampled_at", "received_at", "time"),
    "rx_errors": ("rx_error", "rx_fcs_error", "rx_crc_error"),
    "tx_errors": ("tx_error", "tx_fcs_error", "tx_crc_error"),
}


@dataclass(frozen=True)
class GraphPoint:
    x: str
    y: float

    def to_dict(self) -> dict[str, Any]:
        return {"x": self.x, "y": self.y}


@dataclass(frozen=True)
class GraphSeries:
    name: str
    points: tuple[GraphPoint, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "points": [point.to_dict() for point in self.points],
        }


@dataclass(frozen=True)
class LineGraph:
    kind: str
    title: str
    x: str
    y: str
    group_by: str | None
    x_labels: tuple[str, ...]
    series: tuple[GraphSeries, ...]
    source_count: int
    plotted_count: int
    dropped_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "title": self.title,
            "x": self.x,
            "y": self.y,
            "group_by": self.group_by,
            "x_labels": list(self.x_labels),
            "series": [series.to_dict() for series in self.series],
            "source_count": self.source_count,
            "plotted_count": self.plotted_count,
            "dropped_count": self.dropped_count,
        }


@dataclass(frozen=True)
class BarGraph:
    kind: str
    title: str
    x: str
    y: str
    group_by: str | None
    x_labels: tuple[str, ...]
    series: tuple[GraphSeries, ...]
    source_count: int
    plotted_count: int
    dropped_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "title": self.title,
            "x": self.x,
            "y": self.y,
            "group_by": self.group_by,
            "x_labels": list(self.x_labels),
            "series": [series.to_dict() for series in self.series],
            "source_count": self.source_count,
            "plotted_count": self.plotted_count,
            "dropped_count": self.dropped_count,
        }


def line_graph(
    records: Iterable[Mapping[str, Any] | object] | Mapping[str, Any] | object,
    *,
    y: Field | Sequence[Field],
    x: Field | None = None,
    group_by: Field | Sequence[Field] | None = None,
    title: str | None = None,
    sample_at: Any | None = None,
    aliases: FieldAliases | None = None,
    fields: DerivedFields | None = None,
    where: RecordFilter | None = None,
) -> LineGraph:
    """Build a line graph from records or an operation result.

    If ``records`` is an :class:`network_lang.OperationResult`, the graph is
    built from ``records.data``. When ``x`` is omitted, each row is treated as a
    current snapshot and assigned ``sample_at`` or the current UTC time.
    """
    y_fields = _field_tuple(y)
    x_field = x or "timestamp"
    alias_map = _alias_map(aliases)
    sample_value = _sample_value(x, sample_at)
    source_count = 0
    plotted_count = 0
    plotted_rows = 0

    groups: dict[str, list[tuple[tuple[int, float], int, str, float]]] = {}
    x_label_sort: dict[str, tuple[int, float]] = {}
    x_label_index: dict[str, int] = {}

    for index, record in enumerate(_record_rows(records)):
        source_count += 1
        if where is not None and not where(record):
            continue

        x_value = _field_value(record, x_field, aliases=alias_map, fields=fields)
        if x_value is None:
            x_value = sample_value
        group = _series_group(record, group_by, aliases=alias_map, fields=fields)
        if x_value is None:
            continue

        row_plotted = False
        for y_field in y_fields:
            y_value = _field_value(record, y_field, aliases=alias_map, fields=fields)
            y_number = _float_value(y_value)
            if y_number is None:
                continue

            x_label = _label(x_value)
            sort_key = _x_sort_key(x_value, index)
            series_name = _line_series_name(group, y_field, len(y_fields))

            groups.setdefault(series_name, []).append(
                (sort_key, index, x_label, y_number)
            )

            if x_label not in x_label_sort or sort_key < x_label_sort[x_label]:
                x_label_sort[x_label] = sort_key
                x_label_index[x_label] = index

            plotted_count += 1
            row_plotted = True
        if row_plotted:
            plotted_rows += 1

    x_labels = tuple(
        label
        for label, _ in sorted(
            x_label_sort.items(),
            key=lambda item: (item[1], x_label_index.get(item[0], 0), item[0]),
        )
    )

    series = []
    for name in sorted(groups):
        ordered = sorted(groups[name], key=lambda item: (item[0], item[1], item[2]))
        latest: dict[str, float] = {}
        for _, _, x_label, y_number in ordered:
            latest[x_label] = y_number
        points = tuple(
            GraphPoint(x=label, y=latest[label])
            for label in x_labels
            if label in latest
        )
        series.append(GraphSeries(name=name, points=points))

    y_label = _field_display(y_fields)
    x_label = _field_name(x_field)
    group_label = _field_display(_field_tuple(group_by)) if group_by else None
    graph_title = title or f"{y_label} by {x_label}"
    return LineGraph(
        kind="line",
        title=graph_title,
        x=x_label,
        y=y_label,
        group_by=group_label,
        x_labels=x_labels,
        series=tuple(series),
        source_count=source_count,
        plotted_count=plotted_count,
        dropped_count=source_count - plotted_rows,
    )


def bar_graph(
    records: Iterable[Mapping[str, Any] | object] | Mapping[str, Any] | object,
    *,
    x: Field,
    y: Field | None = None,
    group_by: Field | Sequence[Field] | None = None,
    title: str | None = None,
    aggregate: str = "count",
    aliases: FieldAliases | None = None,
    fields: DerivedFields | None = None,
    where: RecordFilter | None = None,
) -> BarGraph:
    """Build a bar graph from numeric values or categorical record counts.

    Args:
        records:
        x:
        y:
        group_by:
        title:
        aggregate:
        aliases:
        fields:
        where:
    """
    alias_map = _alias_map(aliases)
    effective_aggregate = "sum" if y is not None and aggregate == "count" else aggregate
    source_count = 0
    plotted_count = 0
    buckets: dict[str, dict[str, list[float]]] = {}
    x_order: dict[str, int] = {}

    for index, record in enumerate(_record_rows(records)):
        source_count += 1
        if where is not None and not where(record):
            continue

        x_value = _field_value(record, x, aliases=alias_map, fields=fields)
        if x_value is None:
            continue

        group = _series_group(record, group_by, aliases=alias_map, fields=fields)
        y_value = 1.0 if y is None else _field_value(
            record,
            y,
            aliases=alias_map,
            fields=fields,
        )
        y_number = _float_value(y_value)
        if y_number is None:
            continue

        x_label = _label(x_value)
        x_order.setdefault(x_label, index)
        buckets.setdefault(group, {}).setdefault(x_label, []).append(y_number)
        plotted_count += 1

    x_labels = tuple(sorted(x_order, key=lambda label: (x_order[label], label)))
    series = []
    for name in sorted(buckets):
        points = tuple(
            GraphPoint(
                x=label,
                y=_aggregate_values(buckets[name][label], effective_aggregate),
            )
            for label in x_labels
            if label in buckets[name]
        )
        series.append(GraphSeries(name=name, points=points))

    x_label = _field_name(x)
    y_label = _field_name(y) if y else effective_aggregate
    group_label = _field_display(_field_tuple(group_by)) if group_by else None
    graph_title = title or f"{y_label} by {x_label}"
    return BarGraph(
        kind="bar",
        title=graph_title,
        x=x_label,
        y=y_label,
        group_by=group_label,
        x_labels=x_labels,
        series=tuple(series),
        source_count=source_count,
        plotted_count=plotted_count,
        dropped_count=source_count - plotted_count,
    )


def counter_rate_records(
    records: Iterable[Mapping[str, Any] | object] | Mapping[str, Any] | object,
    *,
    counters: Field | Sequence[Field],
    group_by: Field | Sequence[Field] | None,
    x: Field = "timestamp",
    scale: float = 1.0,
    suffix: str = "_rate",
    aliases: FieldAliases | None = None,
    fields: DerivedFields | None = None,
    where: RecordFilter | None = None,
) -> tuple[dict[str, Any], ...]:
    """Convert cumulative counters into sampled rates.

    RouterOS byte and packet values are counters. Plotting them directly often
    looks flat because the absolute values are huge. This helper compares each
    row with the previous row in the same group and adds derived fields such as
    ``rx_mbps`` or ``tx_rate``.
    """
    counter_fields = _field_tuple(counters)
    if not counter_fields:
        return ()

    alias_map = _alias_map(aliases)
    grouped: dict[str, list[tuple[float, int, Mapping[str, Any] | object]]] = {}

    for index, record in enumerate(_record_rows(records)):
        if where is not None and not where(record):
            continue

        x_value = _field_value(record, x, aliases=alias_map, fields=fields)
        timestamp = _time_value(x_value)
        if timestamp is None:
            continue

        group = _series_group(record, group_by, aliases=alias_map, fields=fields)
        grouped.setdefault(group, []).append((timestamp, index, record))

    rated_rows: list[dict[str, Any]] = []
    for group in sorted(grouped):
        previous: dict[str, tuple[float, float]] = {}
        for timestamp, _, record in sorted(grouped[group], key=lambda item: item[:2]):
            row = _record_dict(record)
            has_rate = False

            for counter in counter_fields:
                counter_name = _field_name(counter)
                counter_value = _float_value(
                    _field_value(record, counter, aliases=alias_map, fields=fields)
                )
                if counter_value is None:
                    continue

                previous_value = previous.get(counter_name)
                if previous_value is not None:
                    previous_timestamp, previous_counter = previous_value
                    elapsed = timestamp - previous_timestamp
                    delta = counter_value - previous_counter
                    if elapsed > 0 and delta >= 0:
                        row[counter_rate_field_name(counter, suffix=suffix)] = (
                            delta / elapsed
                        ) * scale
                        has_rate = True

                previous[counter_name] = (timestamp, counter_value)

            if has_rate:
                rated_rows.append(row)

    return tuple(rated_rows)


def counter_rate_field_name(counter: Field, *, suffix: str = "_rate") -> str:
    """Return the field name produced by :func:`counter_rate_records`."""
    name = _field_name(counter)
    if not suffix:
        return name
    if suffix == "_mbps":
        normalized = name.replace("-", "_")
        for ending in ("_bytes", "_byte"):
            if normalized.endswith(ending):
                return f"{normalized[:-len(ending)]}{suffix}"
        return f"{normalized}{suffix}"
    return f"{name}{suffix}"


def _record_rows(
    records: Iterable[Mapping[str, Any] | object] | Mapping[str, Any] | object,
) -> tuple[Mapping[str, Any] | object, ...]:
    if isinstance(records, OperationResult):
        return _record_rows(records.data)
    if records is None:
        return ()
    if isinstance(records, Mapping):
        return (records,)
    if isinstance(records, (str, bytes)):
        return ()
    try:
        return tuple(records)  # type: ignore[arg-type]
    except TypeError:
        return (records,)


def _record_dict(record: Mapping[str, Any] | object) -> dict[str, Any]:
    if isinstance(record, Mapping):
        return dict(record)
    return {"record": record}


def _field_value(
    record: Mapping[str, Any] | object,
    field: Field | None,
    *,
    aliases: FieldAliases,
    fields: DerivedFields | None,
) -> Any:
    if callable(field):
        return field(record)
    if isinstance(field, str) and fields and field in fields:
        return fields[field](record)
    return _record_value(record, field, aliases=aliases, fields=fields)


def _record_value(
    record: Mapping[str, Any] | object,
    key: str | None,
    *,
    aliases: FieldAliases,
    fields: DerivedFields | None,
) -> Any:
    if key is None:
        return None

    value = _single_value_with_aliases(record, key, aliases=aliases, fields=fields)
    if value is not None:
        return value
    if "." not in key:
        return None

    current: Any = record
    for part in key.split("."):
        current = _single_value_with_aliases(
            current,
            part,
            aliases=aliases,
            fields=fields,
        )
        if current is None:
            return None
    return current


def _single_value_with_aliases(
    record: Any,
    key: str,
    *,
    aliases: FieldAliases,
    fields: DerivedFields | None,
) -> Any:
    if fields and key in fields:
        return fields[key](record)
    value = _single_value(record, key)
    if value is not None:
        return value
    for alias in aliases.get(key, ()):
        value = _single_value(record, alias)
        if value is not None:
            return value
    return None


def _single_value(record: Any, key: str) -> Any:
    if isinstance(record, Mapping):
        if key in record:
            return record.get(key)
        normalized = key.replace("-", "_")
        if normalized in record:
            return record.get(normalized)
        routeros_key = key.replace("_", "-")
        if routeros_key in record:
            return record.get(routeros_key)
        return None
    if hasattr(record, key):
        return getattr(record, key)
    return None


def _float_value(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _label(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=timezone.utc).isoformat().replace(
            "+00:00",
            "Z",
        )
    return str(value)


def _group_label(value: Any) -> str:
    if value is None:
        return "unknown"
    text = str(value).strip()
    return text if text else "unknown"


def _series_group(
    record: Mapping[str, Any] | object,
    group_by: Field | Sequence[Field] | None,
    *,
    aliases: FieldAliases,
    fields: DerivedFields | None,
) -> str:
    if not group_by:
        return "all"
    values = [
        _group_label(_field_value(record, field, aliases=aliases, fields=fields))
        for field in _field_tuple(group_by)
    ]
    return " / ".join(values)


def _line_series_name(group: str, y_field: Field, y_count: int) -> str:
    y_name = _field_name(y_field)
    if group == "all":
        return y_name if y_count > 1 else "all"
    if y_count == 1:
        return group
    return f"{group} / {y_name}"


def _field_tuple(value: Field | Sequence[Field] | None) -> tuple[Field, ...]:
    if value is None:
        return ()
    if isinstance(value, str) or callable(value):
        return (value,)
    return tuple(value)


def _field_name(field: Field | None) -> str:
    if field is None:
        return "value"
    if isinstance(field, str):
        return field
    return getattr(field, "__name__", "value")


def _field_display(fields: Sequence[Field]) -> str:
    return ", ".join(_field_name(field) for field in fields)


def _alias_map(aliases: FieldAliases | None) -> dict[str, tuple[str, ...]]:
    merged = {key: tuple(value) for key, value in _FIELD_ALIASES.items()}
    if aliases:
        for key, value in aliases.items():
            merged[key] = tuple(value) + merged.get(key, ())
    return merged


def _aggregate_values(values: Sequence[float], aggregate: str) -> float:
    if not values:
        return 0.0
    if aggregate == "count":
        return float(len(values))
    if aggregate == "sum":
        return float(sum(values))
    if aggregate == "avg":
        return float(sum(values) / len(values))
    if aggregate == "min":
        return float(min(values))
    if aggregate == "max":
        return float(max(values))
    if aggregate == "latest":
        return float(values[-1])
    raise ValueError(f"unsupported aggregate: {aggregate!r}")


def _sample_value(x: Field | None, sample_at: Any) -> Any:
    if sample_at is not None:
        return sample_at
    return datetime.now(timezone.utc) if x is None else None


def _x_sort_key(value: Any, fallback_index: int) -> tuple[int, float]:
    number = _float_value(value)
    if number is not None:
        return (0, number)

    timestamp = _timestamp(value)
    if timestamp is not None:
        return (1, timestamp)

    return (2, float(fallback_index))


def _timestamp(value: Any) -> float | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.timestamp()
    if isinstance(value, date):
        return datetime.combine(value, time.min, tzinfo=timezone.utc).timestamp()
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _time_value(value: Any) -> float | None:
    timestamp = _timestamp(value)
    if timestamp is not None:
        return timestamp
    return _float_value(value)
