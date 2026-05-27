from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from network_lang import target_device
from network_lang.exporters import to_html
from network_lang.graphing import (
    bar_graph,
    counter_rate_field_name,
    counter_rate_records,
    line_graph,
)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    device = target_device(args.target)

    print(f"target: {device.name} ({device.url})")

    records = _collect_records(device, args)
    if not records:
        print("no graphable records returned", file=sys.stderr)
        return 1

    kind = args.kind
    if kind == "auto":
        kind = "line" if args.samples > 1 else "bar"

    if kind == "bar":
        graph = _bar_graph(records, args)
    else:
        graph = _line_graph(records, args)

    output = args.output or f"{_slug(graph.y)}.html"
    to_html(graph, output)
    print(f"wrote {output} ({graph.plotted_count}/{graph.source_count} points)")
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a standalone HTML graph from a network_lang operation.",
    )
    parser.add_argument(
        "--target",
        default=os.environ.get("NETWORK_LANG_TARGET", "edge-01"),
    )
    parser.add_argument(
        "--operation",
        default=os.environ.get("NETWORK_LANG_GRAPH_OPERATION", "network.interfaces.list"),
    )
    parser.add_argument(
        "--kind",
        choices=("auto", "line", "bar"),
        default=os.environ.get("NETWORK_LANG_GRAPH_KIND", "auto"),
    )
    parser.add_argument(
        "--metric",
        default=os.environ.get("NETWORK_LANG_GRAPH_METRIC", "rx_errors"),
        help="Metric field. Use comma-separated fields for a multi-metric line graph.",
    )
    parser.add_argument(
        "--x",
        default=os.environ.get("NETWORK_LANG_GRAPH_X"),
        help="X field for line graphs, or category field for bar graphs.",
    )
    parser.add_argument(
        "--group-by",
        default=os.environ.get("NETWORK_LANG_GRAPH_GROUP_BY", "interface"),
    )
    parser.add_argument(
        "--match",
        default=os.environ.get("NETWORK_LANG_GRAPH_MATCH", "{}"),
        help='JSON match filter, for example \'{"running":"true"}\'.',
    )
    parser.add_argument(
        "--params",
        default=os.environ.get("NETWORK_LANG_GRAPH_PARAMS", "{}"),
        help="Extra JSON operation params.",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=int(os.environ.get("NETWORK_LANG_GRAPH_SAMPLES", "1")),
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=float(os.environ.get("NETWORK_LANG_GRAPH_INTERVAL", "5")),
    )
    parser.add_argument(
        "--rate",
        action="store_true",
        default=_env_bool("NETWORK_LANG_GRAPH_RATE"),
        help="Treat metric fields as cumulative counters and graph their rate.",
    )
    parser.add_argument(
        "--raw-counters",
        action="store_true",
        default=_env_bool("NETWORK_LANG_GRAPH_RAW_COUNTERS"),
        help="Disable automatic byte-counter rate conversion.",
    )
    parser.add_argument(
        "--rate-scale",
        type=float,
        default=float(os.environ.get("NETWORK_LANG_GRAPH_RATE_SCALE", "0.000008")),
        help="Multiplier applied to counter delta per second. Default converts bytes/sec to Mbps.",
    )
    parser.add_argument(
        "--rate-suffix",
        default=os.environ.get("NETWORK_LANG_GRAPH_RATE_SUFFIX", "_mbps"),
        help="Suffix for derived rate fields.",
    )
    parser.add_argument(
        "--aggregate",
        choices=("count", "sum", "avg", "min", "max", "latest"),
        default=os.environ.get("NETWORK_LANG_GRAPH_AGGREGATE"),
    )
    parser.add_argument(
        "--count",
        action="store_true",
        default=_env_bool("NETWORK_LANG_GRAPH_COUNT"),
        help="Count category occurrences instead of graphing metric values.",
    )
    parser.add_argument(
        "--title",
        default=os.environ.get("NETWORK_LANG_GRAPH_TITLE"),
    )
    parser.add_argument(
        "--output",
        default=os.environ.get("NETWORK_LANG_GRAPH_OUTPUT"),
    )
    return parser.parse_args(argv)


def _collect_records(device: Any, args: argparse.Namespace) -> list[dict[str, Any]]:
    params = _json_object(args.params, "--params")
    match = _json_object(args.match, "--match")
    if match:
        params["match"] = match

    records: list[dict[str, Any]] = []
    for sample in range(args.samples):
        operation = device.operation(args.operation, **params)
        result = device.execute(operation)
        if not result.ok:
            print(json.dumps(result.to_dict(), indent=2), file=sys.stderr)
            raise SystemExit(1)

        sampled_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        for row in _rows(result.data):
            records.append(
                {
                    **row,
                    "timestamp": sampled_at,
                    "sample": sample,
                    "operation": args.operation,
                    "target": device.name,
                }
            )

        if sample + 1 < args.samples:
            time.sleep(args.interval)

    return records


def _line_graph(records: list[dict[str, Any]], args: argparse.Namespace) -> Any:
    metric_fields = _metric_fields(args.metric)
    y = _field_or_fields(args.metric)
    x = args.x or "timestamp"
    group_by = _optional_fields(args.group_by)
    if _should_rate(args, metric_fields):
        if args.samples < 2:
            raise SystemExit("--rate needs at least 2 samples")

        records = list(
            counter_rate_records(
                records,
                counters=metric_fields,
                group_by=group_by,
                x=x,
                scale=args.rate_scale,
                suffix=args.rate_suffix,
            )
        )
        if not records:
            raise SystemExit("not enough ordered counter samples to calculate rates")

        rate_fields = tuple(
            counter_rate_field_name(metric, suffix=args.rate_suffix)
            for metric in metric_fields
        )
        y = rate_fields[0] if len(rate_fields) == 1 else rate_fields
        title = args.title or (
            f"{_title(','.join(rate_fields))} by {_title(args.group_by or x)}"
        )
    else:
        title = args.title or f"{_title(args.metric)} by {_title(args.group_by or x)}"

    return line_graph(
        records,
        x=x,
        y=y,
        group_by=group_by,
        title=title,
    )


def _bar_graph(records: list[dict[str, Any]], args: argparse.Namespace) -> Any:
    group_by = _optional_fields(args.group_by)
    x = args.x or args.group_by or args.metric
    count_mode = args.count or (not args.x and not args.group_by)
    y = None if count_mode else args.metric
    aggregate = args.aggregate or ("count" if y is None else "latest")
    title = args.title or f"{_title(args.metric)} by {_title(x)}"
    return bar_graph(
        records,
        x=x,
        y=y,
        group_by=None if x == args.group_by else group_by,
        title=title,
        aggregate=aggregate,
    )


def _rows(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [dict(row) for row in data if isinstance(row, Mapping)]
    if isinstance(data, Mapping):
        return [dict(data)]
    return []


def _json_object(raw: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{label} must be valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise SystemExit(f"{label} must decode to a JSON object")
    return value


def _field_or_fields(raw: str) -> str | tuple[str, ...]:
    fields = _metric_fields(raw)
    return fields[0] if len(fields) == 1 else fields


def _metric_fields(raw: str) -> tuple[str, ...]:
    fields = tuple(part.strip() for part in raw.split(",") if part.strip())
    if not fields:
        raise SystemExit("--metric cannot be empty")
    return fields


def _optional_fields(raw: str | None) -> str | tuple[str, ...] | None:
    if raw is None:
        return None
    fields = tuple(part.strip() for part in raw.split(",") if part.strip())
    if not fields:
        return None
    return fields[0] if len(fields) == 1 else fields


def _env_bool(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _should_rate(args: argparse.Namespace, metrics: tuple[str, ...]) -> bool:
    if args.raw_counters:
        return False
    if args.rate:
        return True
    return args.samples > 1 and all(_is_byte_counter(metric) for metric in metrics)


def _is_byte_counter(metric: str) -> bool:
    normalized = metric.strip().replace("-", "_")
    return normalized.endswith("_byte") or normalized.endswith("_bytes")


def _title(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").replace(",", ", ").title()


def _slug(value: str) -> str:
    return (
        value.split(",", 1)[0]
        .strip()
        .replace(".", "_")
        .replace("-", "_")
        .replace(" ", "_")
        or "graph"
    )


if __name__ == "__main__":
    raise SystemExit(main())
