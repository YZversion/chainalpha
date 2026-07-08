"""Inline SVG chart helpers (no CDN, no matplotlib)."""

from __future__ import annotations

from collections.abc import Sequence


def _esc(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _scale(
    values: Sequence[float],
    width: int,
    height: int,
    *,
    pad: int = 8,
    ymin: float | None = None,
    ymax: float | None = None,
) -> tuple[list[tuple[float, float]], float, float]:
    if not values:
        return [], 0.0, 1.0
    lo = ymin if ymin is not None else min(values)
    hi = ymax if ymax is not None else max(values)
    if hi == lo:
        hi = lo + 1.0
    inner_w = width - 2 * pad
    inner_h = height - 2 * pad
    pts: list[tuple[float, float]] = []
    n = len(values)
    for i, v in enumerate(values):
        x = pad + (i / max(n - 1, 1)) * inner_w
        y = pad + (1.0 - (v - lo) / (hi - lo)) * inner_h
        pts.append((x, y))
    return pts, lo, hi


def line_chart(
    dates: Sequence[str],
    values: Sequence[float],
    *,
    width: int = 720,
    height: int = 200,
    stroke: str = "#2563eb",
    title: str = "",
    y_format: str = ".0f",
    events: Sequence[dict[str, str]] | None = None,
) -> str:
    if not values:
        return '<svg class="chart-empty" width="720" height="80"><text x="8" y="40">MISSING</text></svg>'

    pts, lo, hi = _scale(values, width, height)
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    date_by_idx = {d: i for i, d in enumerate(dates)}
    markers = []
    if events:
        for ev in events:
            idx = date_by_idx.get(ev["date"])
            if idx is None:
                continue
            x, y = pts[idx]
            color = {"cooldown": "#f59e0b", "setup_disabled": "#dc2626", "system_disabled": "#7c3aed"}.get(
                ev.get("kind", ""), "#64748b"
            )
            markers.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}">'
                f'<title>{_esc(ev.get("label", ""))}</title></circle>'
            )

    return f"""<svg class="chart line-chart" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{_esc(title)}">
  <rect x="0" y="0" width="{width}" height="{height}" fill="#fafafa"/>
  <text x="8" y="14" class="chart-title">{_esc(title)}</text>
  <text x="8" y="{height - 4}" class="chart-axis">{_esc(dates[0])}</text>
  <text x="{width - 8}" y="{height - 4}" class="chart-axis" text-anchor="end">{_esc(dates[-1])}</text>
  <text x="8" y="28" class="chart-axis">max {_esc(format(hi, y_format))}</text>
  <text x="8" y="{height - 18}" class="chart-axis">min {_esc(format(lo, y_format))}</text>
  <polyline fill="none" stroke="{stroke}" stroke-width="2" points="{poly}"/>
  {''.join(markers)}
</svg>"""


def bar_chart_signed(
    dates: Sequence[str],
    values: Sequence[float],
    *,
    width: int = 720,
    height: int = 160,
    title: str = "",
) -> str:
    if not values:
        return '<svg class="chart-empty" width="720" height="80"><text x="8" y="40">MISSING</text></svg>'

    abs_max = max(abs(v) for v in values) or 1.0
    pad = 8
    inner_w = width - 2 * pad
    inner_h = (height - 2 * pad) / 2
    mid_y = height / 2
    n = len(values)
    bar_w = max(inner_w / max(n, 1) * 0.7, 1.0)
    bars = []
    for i, v in enumerate(values):
        x = pad + (i / max(n, 1)) * inner_w + bar_w * 0.15
        h = abs(v) / abs_max * inner_h
        y = mid_y - h if v >= 0 else mid_y
        color = "#16a34a" if v >= 0 else "#dc2626"
        bars.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="{color}"/>')

    return f"""<svg class="chart bar-chart" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{_esc(title)}">
  <rect x="0" y="0" width="{width}" height="{height}" fill="#fafafa"/>
  <text x="8" y="14" class="chart-title">{_esc(title)}</text>
  <line x1="{pad}" y1="{mid_y}" x2="{width - pad}" y2="{mid_y}" stroke="#cbd5e1"/>
  {''.join(bars)}
</svg>"""


def stacked_verdict_bars(
    dates: Sequence[str],
    entered: Sequence[int],
    blocked: Sequence[int],
    unfilled: Sequence[int],
    *,
    width: int = 720,
    height: int = 180,
    title: str = "Daily candidate verdicts",
) -> str:
    if not dates:
        return '<svg class="chart-empty" width="720" height="80"><text x="8" y="40">MISSING</text></svg>'

    totals = [e + b + u for e, b, u in zip(entered, blocked, unfilled)]
    max_total = max(totals) or 1
    pad = 8
    inner_w = width - 2 * pad
    inner_h = height - 2 * pad - 16
    n = len(dates)
    bar_w = max(inner_w / max(n, 1) * 0.7, 1.0)
    rects = []
    for i, (e, b, u) in enumerate(zip(entered, blocked, unfilled)):
        x = pad + (i / max(n, 1)) * inner_w + bar_w * 0.15
        total = e + b + u
        if total == 0:
            continue
        y_base = height - pad
        for val, color in ((u, "#94a3b8"), (b, "#f59e0b"), (e, "#16a34a")):
            if val == 0:
                continue
            h = val / max_total * inner_h
            y_base -= h
            rects.append(
                f'<rect x="{x:.1f}" y="{y_base:.1f}" width="{bar_w:.1f}" height="{h:.1f}" fill="{color}"/>'
            )

    return f"""<svg class="chart stacked-chart" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{_esc(title)}">
  <rect x="0" y="0" width="{width}" height="{height}" fill="#fafafa"/>
  <text x="8" y="14" class="chart-title">{_esc(title)}</text>
  <text x="{width - 8}" y="14" class="chart-legend" text-anchor="end">■ entered ■ blocked ■ unfilled</text>
  {''.join(rects)}
</svg>"""


def sparkline(
    values: Sequence[float],
    *,
    width: int = 200,
    height: int = 48,
    stroke: str = "#2563eb",
    threshold: float | None = None,
) -> str:
    if not values:
        return '<svg width="200" height="48"><text x="4" y="24">—</text></svg>'

    pts, lo, hi = _scale(values, width, height, pad=4)
    if threshold is not None:
        pad = 4
        inner_h = height - 2 * pad
        if hi == lo:
            hi = lo + 1.0
        ty = pad + (1.0 - (threshold - lo) / (hi - lo)) * inner_h
        thresh_line = f'<line x1="4" y1="{ty:.1f}" x2="{width - 4}" y2="{ty:.1f}" stroke="#dc2626" stroke-dasharray="3,3"/>'
    else:
        thresh_line = ""
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    return f"""<svg class="sparkline" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  {thresh_line}
  <polyline fill="none" stroke="{stroke}" stroke-width="1.5" points="{poly}"/>
</svg>"""
