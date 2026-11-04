#!/usr/bin/env python3
"""Plot QPS and mean per-query latency across an efSearch sweep."""

import argparse
import csv
from collections import defaultdict
from html import escape
from pathlib import Path

from plot_ef_search_sweep_svg import CONFIGS, EF_VALUES


def read_points(run_dir):
    points = defaultdict(dict)
    with (run_dir / "comparison.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            config, ef = row["configuration"], int(row["efSearch"])
            if config not in {item[0] for item in CONFIGS} or ef not in EF_VALUES:
                raise ValueError(f"Unexpected configuration or efSearch: {config}, {ef}")
            if ef in points[config]:
                raise ValueError(f"Duplicate point: {config}, {ef}")
            qps = float(row["mean_qps"])
            latency_ms = float(row["mean_latency_us"]) / 1000
            if qps <= 0 or latency_ms <= 0:
                raise ValueError(f"Invalid QPS or latency: {config}, {ef}")
            points[config][ef] = (qps, latency_ms)
    if any(set(points[config]) != set(EF_VALUES) for config, *_ in CONFIGS):
        raise ValueError("Expected all ten efSearch values for every configuration")
    return points


def chart(points, metric, title, ylabel, maximum, ticks):
    width, height = 940, 620
    left, top, right, bottom = 95, 70, 890, 465
    x = lambda index: left + (right - left) * index / (len(EF_VALUES) - 1)
    y = lambda value: bottom - (bottom - top) * value / maximum
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{escape(title)} for five SIFT1M configurations">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<g font-family="DejaVu Sans,Arial,sans-serif" fill="#222">',
        f'<text x="470" y="32" text-anchor="middle" font-size="20" font-weight="bold">{escape(title)}</text>',
        '<text x="470" y="52" text-anchor="middle" font-size="12" fill="#555">'
        'SIFT1M · M=48 · efConstruction=80 · k=20 · five repeats per point</text>',
    ]
    for index, ef in enumerate(EF_VALUES):
        px = x(index)
        parts += [f'<line x1="{px:.1f}" y1="{top}" x2="{px:.1f}" y2="{bottom}" stroke="#f0f0f0"/>',
                  f'<text x="{px:.1f}" y="{bottom + 24}" text-anchor="middle" font-size="12">{ef}</text>']
    for tick in ticks:
        py = y(tick)
        label = f"{tick:,.0f}" if maximum > 100 else f"{tick:g}"
        parts += [f'<line x1="{left}" y1="{py:.1f}" x2="{right}" y2="{py:.1f}" stroke="#e6e6e6"/>',
                  f'<text x="{left - 12}" y="{py + 4:.1f}" text-anchor="end" font-size="12">{label}</text>']
    parts += [f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="#555"/>',
              f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="#555"/>',
              f'<text x="{(left + right) / 2:.1f}" y="{bottom + 52}" text-anchor="middle" font-size="14">efSearch</text>',
              f'<text transform="translate(27 {(top + bottom) / 2:.1f}) rotate(-90)" text-anchor="middle" font-size="14">{escape(ylabel)}</text>']
    for config, label, color, dash, marker in CONFIGS:
        values = [points[config][ef][metric] for ef in EF_VALUES]
        polyline = " ".join(f"{x(index):.2f},{y(value):.2f}" for index, value in enumerate(values))
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        parts.append(f'<polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="2"{dash_attr}/>')
        for index, value in enumerate(values):
            px, py = x(index), y(value)
            if marker == "diamond":
                parts.append(f'<path d="M {px:.2f} {py-4:.2f} L {px+4:.2f} {py:.2f} L {px:.2f} {py+4:.2f} L {px-4:.2f} {py:.2f} Z" fill="white" stroke="{color}" stroke-width="1.5"/>')
            elif marker == "circle":
                parts.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="3.5" fill="white" stroke="{color}" stroke-width="1.5"/>')
            else:
                parts.append(f'<path d="M {px:.2f} {py-4:.2f} L {px+4:.2f} {py+3:.2f} L {px-4:.2f} {py+3:.2f} Z" fill="white" stroke="{color}" stroke-width="1.5"/>')
    for index, (_, label, color, dash, marker) in enumerate(CONFIGS):
        lx = 115 + (index % 2) * 280
        ly = 535 + (index // 2) * 23
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        parts.append(f'<line x1="{lx}" y1="{ly}" x2="{lx+28}" y2="{ly}" stroke="{color}" stroke-width="2"{dash_attr}/>')
        if marker == "diamond":
            parts.append(f'<path d="M {lx+14} {ly-4} l 4 4 -4 4 -4 -4 Z" fill="white" stroke="{color}" stroke-width="1.5"/>')
        elif marker == "circle":
            parts.append(f'<circle cx="{lx+14}" cy="{ly}" r="3.5" fill="white" stroke="{color}" stroke-width="1.5"/>')
        else:
            parts.append(f'<path d="M {lx+14} {ly-4} l 4 7 -8 0 Z" fill="white" stroke="{color}" stroke-width="1.5"/>')
        parts.append(f'<text x="{lx+37}" y="{ly+4}" font-size="12">{escape(label)}</text>')
    parts.append('</g></svg>')
    return "\n".join(parts) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    run_dir = parser.parse_args().run_dir
    points = read_points(run_dir)
    output_dir = run_dir / "plots"
    output_dir.mkdir(exist_ok=True)
    charts = (
        ("qps_five_configs.svg", 0, "Search throughput by efSearch", "Queries per second (QPS)", 10000, range(0, 10001, 2000)),
        ("mean_latency_per_query_five_configs.svg", 1, "Mean latency per query by efSearch", "Mean latency per query (ms)", 3.5, (0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5)),
    )
    for filename, metric, title, ylabel, maximum, ticks in charts:
        output = output_dir / filename
        output.write_text(chart(points, metric, title, ylabel, maximum, ticks))
        print(output)


if __name__ == "__main__":
    main()
