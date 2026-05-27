from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from .graphing import BarGraph, LineGraph

_PALETTE = (
    "#0F766E",
    "#2563EB",
    "#D97706",
    "#BE123C",
    "#047857",
    "#7C3AED",
    "#1D4ED8",
    "#B45309",
    "#0E7490",
    "#C2410C",
)


def to_html(
    graph: LineGraph | BarGraph,
    path: str | Path,
    *,
    width: int = 960,
    height: int = 480,
) -> Path:
    if graph.kind == "line":
        document = _line_graph_html(graph, width=width, height=height)
    elif graph.kind == "bar":
        document = _bar_graph_html(graph, width=width, height=height)
    else:
        raise ValueError(f"unsupported graph kind: {graph.kind!r}")

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
    return output


def _line_graph_html(graph: LineGraph, *, width: int, height: int) -> str:
    margin_left = 70
    margin_right = 24
    margin_top = 40
    margin_bottom = 64

    plot_width = max(width - margin_left - margin_right, 200)
    plot_height = max(height - margin_top - margin_bottom, 120)

    y_values = [point.y for series in graph.series for point in series.points]
    y_min, y_max = _value_range(y_values)
    notice = _flat_value_notice(y_values)

    x_index = {label: index for index, label in enumerate(graph.x_labels)}
    x_count = max(len(graph.x_labels), 1)
    x_step = plot_width / (x_count - 1) if x_count > 1 else 0.0

    def x_pos(label: str) -> float:
        if x_count == 1:
            return margin_left + (plot_width / 2.0)
        return margin_left + x_index.get(label, 0) * x_step

    def y_pos(value: float) -> float:
        scale = (value - y_min) / (y_max - y_min)
        return margin_top + (1.0 - scale) * plot_height

    zero_y = y_pos(0.0) if y_min <= 0 <= y_max else margin_top + plot_height

    y_ticks = []
    for index in range(5):
        ratio = index / 4
        value = y_max - ((y_max - y_min) * ratio)
        y = margin_top + plot_height * ratio
        y_ticks.append((y, _fmt_number(value)))

    x_ticks = []
    max_x_ticks = 10
    for index, label in enumerate(graph.x_labels):
        if x_count > max_x_ticks and index % max(1, x_count // max_x_ticks) != 0:
            continue
        x_ticks.append((x_pos(label), label))
    if graph.x_labels and x_ticks and x_ticks[-1][1] != graph.x_labels[-1]:
        label = graph.x_labels[-1]
        x_ticks.append((x_pos(label), label))

    lines = []
    legend = []
    for index, series in enumerate(graph.series):
        color = _PALETTE[index % len(_PALETTE)]
        path_points = [
            f"{x_pos(point.x):.2f},{y_pos(point.y):.2f}" for point in series.points
        ]
        if not path_points:
            continue
        lines.append(
            (
                f'<polyline class="series-line" stroke="{color}" '
                f'points="{" ".join(path_points)}" />'
            )
        )
        for point in series.points:
            tooltip_x = _tooltip_label(point.x, graph.x_labels)
            lines.append(
                (
                    f'<circle class="series-dot" cx="{x_pos(point.x):.2f}" '
                    f'cy="{y_pos(point.y):.2f}" r="3" fill="{color}">'
                    f"<title>{escape(series.name)} | {escape(tooltip_x)} | "
                    f"{escape(_fmt_number(point.y))}</title></circle>"
                )
            )
        legend.append(
            (
                '<div class="legend-item">'
                f'<span class="legend-swatch" style="background:{color};"></span>'
                f"<span>{escape(series.name)}</span>"
                "</div>"
            )
        )

    y_grid = "\n".join(
        [
            (
                f'<line x1="{margin_left}" y1="{y:.2f}" x2="{margin_left + plot_width}" '
                f'y2="{y:.2f}" class="grid-line" />'
                f'<text x="{margin_left - 10}" y="{y + 4:.2f}" class="axis-label y-label">'
                f"{escape(label)}</text>"
            )
            for y, label in y_ticks
        ]
    )
    x_grid = "\n".join(
        [
            (
                f'<line x1="{x:.2f}" y1="{margin_top}" x2="{x:.2f}" '
                f'y2="{margin_top + plot_height}" class="grid-line x-grid" />'
                f'<text x="{x:.2f}" y="{margin_top + plot_height + 24}" class="axis-label x-label">'
                f"{escape(_axis_label(label, graph.x_labels))}</text>"
            )
            for x, label in x_ticks
        ]
    )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(graph.title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f8fafc;
      --panel: #ffffff;
      --text: #0f172a;
      --muted: #475569;
      --grid: #e2e8f0;
      --axis: #cbd5e1;
    }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Noto Sans", "Liberation Sans", sans-serif;
      background: radial-gradient(circle at top right, #e0f2fe, var(--bg) 58%);
      color: var(--text);
    }}
    .wrap {{
      max-width: {width + 80}px;
      margin: 24px auto;
      padding: 0 16px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      box-shadow: 0 8px 18px rgba(15, 23, 42, 0.05);
      padding: 16px;
    }}
    h1 {{
      margin: 0 0 6px 0;
      font-size: 20px;
      font-weight: 700;
      line-height: 1.25;
    }}
    .meta {{
      margin: 0 0 14px 0;
      color: var(--muted);
      font-size: 13px;
    }}
    .notice {{
      margin: -4px 0 14px 0;
      color: #9a3412;
      font-size: 13px;
    }}
    .legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px 14px;
      margin: 10px 0 0 0;
      font-size: 13px;
      color: var(--text);
    }}
    .legend-item {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }}
    .legend-swatch {{
      width: 12px;
      height: 12px;
      border-radius: 2px;
      display: inline-block;
    }}
    svg {{
      width: 100%;
      height: auto;
      background: #fff;
      border-radius: 8px;
    }}
    .grid-line {{
      stroke: var(--grid);
      stroke-width: 1;
    }}
    .x-grid {{
      stroke-dasharray: 3 4;
    }}
    .axis-border {{
      stroke: var(--axis);
      stroke-width: 1;
    }}
    .axis-label {{
      font-size: 11px;
      fill: #64748b;
    }}
    .x-label {{
      text-anchor: middle;
    }}
    .y-label {{
      text-anchor: end;
    }}
    .series-line {{
      fill: none;
      stroke-width: 2.25;
      stroke-linejoin: round;
      stroke-linecap: round;
    }}
    .series-dot {{
      stroke: #fff;
      stroke-width: 1.25;
    }}
  </style>
</head>
<body>
  <main class="wrap">
    <section class="panel">
      <h1>{escape(graph.title)}</h1>
      <p class="meta">x: {escape(graph.x)} | y: {escape(graph.y)} | records: {graph.plotted_count}/{graph.source_count}</p>
      {_notice_html(notice)}
      <svg viewBox="0 0 {width} {height}" role="img" aria-label="{escape(graph.title)}">
        <rect x="{margin_left}" y="{margin_top}" width="{plot_width}" height="{plot_height}" fill="#ffffff" />
        {y_grid}
        {x_grid}
        <line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + plot_height}" class="axis-border" />
        <line x1="{margin_left}" y1="{zero_y:.2f}" x2="{margin_left + plot_width}" y2="{zero_y:.2f}" class="axis-border" />
        {"".join(lines)}
      </svg>
      <div class="legend">{''.join(legend)}</div>
    </section>
  </main>
</body>
</html>
"""
    return html


def _bar_graph_html(graph: BarGraph, *, width: int, height: int) -> str:
    margin_left = 70
    margin_right = 24
    margin_top = 40
    margin_bottom = 78

    plot_width = max(width - margin_left - margin_right, 200)
    plot_height = max(height - margin_top - margin_bottom, 120)

    y_values = [point.y for series in graph.series for point in series.points]
    y_min, y_max = _value_range(y_values, include_zero=True)
    notice = _flat_value_notice(y_values)

    x_index = {label: index for index, label in enumerate(graph.x_labels)}
    x_count = max(len(graph.x_labels), 1)
    series_count = max(len(graph.series), 1)
    category_width = plot_width / x_count
    bar_width = max(2.0, min(34.0, category_width / (series_count + 1.2)))

    def x_pos(label: str, series_index: int) -> float:
        base = margin_left + x_index.get(label, 0) * category_width
        group_width = bar_width * series_count
        group_offset = (category_width - group_width) / 2.0
        return base + group_offset + (series_index * bar_width)

    def y_pos(value: float) -> float:
        scale = (value - y_min) / (y_max - y_min)
        return margin_top + (1.0 - scale) * plot_height

    zero_y = y_pos(0.0)
    y_ticks = []
    for index in range(5):
        ratio = index / 4
        value = y_max - ((y_max - y_min) * ratio)
        y = margin_top + plot_height * ratio
        y_ticks.append((y, _fmt_number(value)))

    bars = []
    legend = []
    for series_index, series in enumerate(graph.series):
        color = _PALETTE[series_index % len(_PALETTE)]
        for point in series.points:
            tooltip_x = _tooltip_label(point.x, graph.x_labels)
            x = x_pos(point.x, series_index)
            y = y_pos(max(point.y, 0.0))
            bar_height = abs(zero_y - y_pos(point.y))
            bars.append(
                (
                    f'<rect class="bar" x="{x:.2f}" y="{y:.2f}" '
                    f'width="{bar_width * 0.86:.2f}" height="{bar_height:.2f}" '
                    f'fill="{color}"><title>{escape(series.name)} | '
                    f"{escape(tooltip_x)} | {escape(_fmt_number(point.y))}"
                    "</title></rect>"
                )
            )
        legend.append(
            (
                '<div class="legend-item">'
                f'<span class="legend-swatch" style="background:{color};"></span>'
                f"<span>{escape(series.name)}</span>"
                "</div>"
            )
        )

    y_grid = "\n".join(
        [
            (
                f'<line x1="{margin_left}" y1="{y:.2f}" x2="{margin_left + plot_width}" '
                f'y2="{y:.2f}" class="grid-line" />'
                f'<text x="{margin_left - 10}" y="{y + 4:.2f}" class="axis-label y-label">'
                f"{escape(label)}</text>"
            )
            for y, label in y_ticks
        ]
    )
    x_labels = "\n".join(
        [
            (
                f'<text x="{margin_left + (index + 0.5) * category_width:.2f}" '
                f'y="{margin_top + plot_height + 24}" class="axis-label x-label">'
                f"{escape(_axis_label(label, graph.x_labels, max_chars=18))}</text>"
            )
            for index, label in enumerate(graph.x_labels)
        ]
    )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(graph.title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f8fafc;
      --panel: #ffffff;
      --text: #0f172a;
      --muted: #475569;
      --grid: #e2e8f0;
      --axis: #cbd5e1;
    }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Noto Sans", "Liberation Sans", sans-serif;
      background: radial-gradient(circle at top right, #ecfeff, var(--bg) 58%);
      color: var(--text);
    }}
    .wrap {{
      max-width: {width + 80}px;
      margin: 24px auto;
      padding: 0 16px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid #e2e8f0;
      border-radius: 10px;
      box-shadow: 0 8px 18px rgba(15, 23, 42, 0.05);
      padding: 16px;
    }}
    h1 {{
      margin: 0 0 6px 0;
      font-size: 20px;
      font-weight: 700;
      line-height: 1.25;
    }}
    .meta {{
      margin: 0 0 14px 0;
      color: var(--muted);
      font-size: 13px;
    }}
    .notice {{
      margin: -4px 0 14px 0;
      color: #9a3412;
      font-size: 13px;
    }}
    .legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px 14px;
      margin: 10px 0 0 0;
      font-size: 13px;
      color: var(--text);
    }}
    .legend-item {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }}
    .legend-swatch {{
      width: 12px;
      height: 12px;
      border-radius: 2px;
      display: inline-block;
    }}
    svg {{
      width: 100%;
      height: auto;
      background: #fff;
      border-radius: 8px;
    }}
    .grid-line {{
      stroke: var(--grid);
      stroke-width: 1;
    }}
    .axis-border {{
      stroke: var(--axis);
      stroke-width: 1;
    }}
    .axis-label {{
      font-size: 11px;
      fill: #64748b;
    }}
    .x-label {{
      text-anchor: middle;
    }}
    .y-label {{
      text-anchor: end;
    }}
    .bar {{
      rx: 2px;
    }}
  </style>
</head>
<body>
  <main class="wrap">
    <section class="panel">
      <h1>{escape(graph.title)}</h1>
      <p class="meta">x: {escape(graph.x)} | y: {escape(graph.y)} | records: {graph.plotted_count}/{graph.source_count}</p>
      {_notice_html(notice)}
      <svg viewBox="0 0 {width} {height}" role="img" aria-label="{escape(graph.title)}">
        <rect x="{margin_left}" y="{margin_top}" width="{plot_width}" height="{plot_height}" fill="#ffffff" />
        {y_grid}
        {x_labels}
        <line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + plot_height}" class="axis-border" />
        <line x1="{margin_left}" y1="{zero_y:.2f}" x2="{margin_left + plot_width}" y2="{zero_y:.2f}" class="axis-border" />
        {"".join(bars)}
      </svg>
      <div class="legend">{''.join(legend)}</div>
    </section>
  </main>
</body>
</html>
"""
    return html


def _fmt_number(value: float) -> str:
    if abs(value) >= 1000:
        return f"{value:,.2f}".rstrip("0").rstrip(".")
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _value_range(
    values: list[float],
    *,
    include_zero: bool = False,
) -> tuple[float, float]:
    if not values:
        return (0.0, 1.0)

    y_min = min(values)
    y_max = max(values)
    if include_zero:
        y_min = min(0.0, y_min)
        y_max = max(0.0, y_max)

    if y_min == y_max:
        value = y_min
        if value == 0:
            return (0.0, 1.0)
        if value > 0:
            return (0.0, value * 1.1)
        return (value * 1.1, 0.0)

    span = y_max - y_min
    padding = span * 0.05
    y_min -= padding
    y_max += padding
    if include_zero:
        y_min = min(0.0, y_min)
        y_max = max(0.0, y_max)
    return (y_min, y_max)


def _flat_value_notice(values: list[float]) -> str | None:
    if not values:
        return None
    first = values[0]
    if all(value == first for value in values):
        return f"All plotted values are {_fmt_number(first)}, so series overlap."
    return None


def _notice_html(notice: str | None) -> str:
    if not notice:
        return ""
    return f'<p class="notice">{escape(notice)}</p>'


def _trim_label(value: str, max_chars: int = 24) -> str:
    text = value.strip()
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 3]}..."


def _axis_label(value: str, all_values: tuple[str, ...], *, max_chars: int = 24) -> str:
    timestamp = _parse_timestamp(value)
    if timestamp is None:
        return _trim_label(value, max_chars)

    timestamps = [_parse_timestamp(item) for item in all_values]
    known_dates = {item.date() for item in timestamps if item is not None}
    if len(known_dates) <= 1:
        return timestamp.strftime("%H:%M:%S")
    return timestamp.strftime("%m-%d %H:%M")


def _tooltip_label(value: str, all_values: tuple[str, ...]) -> str:
    timestamp = _parse_timestamp(value)
    if timestamp is None:
        return value

    timestamps = [_parse_timestamp(item) for item in all_values]
    known_dates = {item.date() for item in timestamps if item is not None}
    if len(known_dates) <= 1:
        return timestamp.strftime("%H:%M:%S")
    return timestamp.strftime("%Y-%m-%d %H:%M:%S")


def _parse_timestamp(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None
