#!/usr/bin/env python3
"""Render the four-configuration efSearch recall/latency comparison as SVG."""

import argparse
import csv
from collections import defaultdict
from html import escape
from pathlib import Path


CONFIGS = (
    ("hnsw_off", "HNSW, hints off", "#242424", "6 4", "diamond"),
    ("hnsw_native", "HNSW, native hints", "#242424", "", "diamond"),
    ("shg_baseline", "SHG, hints off", "#c62828", "6 4", "circle"),
    ("shg_lookahead", "SHG, lookahead", "#c62828", "", "circle"),
)
EF_VALUES = (20, 24, 32, 48, 64, 96, 128, 192, 256, 512)


def render(run_dir):
    source = run_dir / "comparison.csv"
    with source.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    points = defaultdict(dict)
    for row in rows:
        config, ef = row["configuration"], int(row["efSearch"])
        if config not in {item[0] for item in CONFIGS} or ef not in EF_VALUES:
            raise ValueError(f"Unexpected configuration or efSearch: {config}, {ef}")
        if ef in points[config]:
            raise ValueError(f"Duplicate point: {config}, {ef}")
        recall = float(row["recall@20"])
        latency = float(row["mean_latency_us"]) / 1000
        if not (0 <= recall <= 1 and latency > 0):
            raise ValueError(f"Invalid recall or latency: {config}, {ef}")
        points[config][ef] = (latency, recall)
    if any(set(points[config]) != set(EF_VALUES) for config, *_ in CONFIGS):
        raise ValueError("Expected all ten efSearch values for all four configurations")

    width, height = 940, 590
    left, top, right, bottom = 85, 70, 890, 475
    x_max, y_min = 3.5, 0.75
    x = lambda ms: left + (right - left) * ms / x_max
    y = lambda recall: bottom - (bottom - top) * (recall - y_min) / (1 - y_min)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" '
        'aria-label="Recall at 20 versus mean search latency for four SIFT1M configurations">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<g font-family="DejaVu Sans,Arial,sans-serif" fill="#222">',
        '<text x="470" y="32" text-anchor="middle" font-size="20" font-weight="bold">'
        'SIFT1M recall–latency tradeoff</text>',
        '<text x="470" y="52" text-anchor="middle" font-size="12" fill="#555">'
        'M=48 · efConstruction=80 · k=20 · five repeats per point</text>',
    ]
    for tick in (0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5):
        px = x(tick)
        parts += [f'<line x1="{px:.1f}" y1="{top}" x2="{px:.1f}" y2="{bottom}" stroke="#e8e8e8"/>',
                  f'<text x="{px:.1f}" y="{bottom + 24}" text-anchor="middle" font-size="12">{tick:g}</text>']
    for tick in (0.75, 0.8, 0.85, 0.9, 0.95, 1):
        py = y(tick)
        parts += [f'<line x1="{left}" y1="{py:.1f}" x2="{right}" y2="{py:.1f}" stroke="#e8e8e8"/>',
                  f'<text x="{left - 12}" y="{py + 4:.1f}" text-anchor="end" font-size="12">{tick:.2f}</text>']
    parts += [f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="#555"/>',
              f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="#555"/>',
              f'<text x="{(left + right) / 2:.1f}" y="{bottom + 53}" text-anchor="middle" font-size="14">Mean latency (ms)</text>',
              f'<text transform="translate(27 {(top + bottom) / 2:.1f}) rotate(-90)" text-anchor="middle" font-size="14">Recall@20</text>']
    for config, label, color, dash, marker in CONFIGS:
        coordinates = [points[config][ef] for ef in EF_VALUES]
        polyline = " ".join(f"{x(ms):.2f},{y(recall):.2f}" for ms, recall in coordinates)
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        parts.append(f'<polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="2"{dash_attr}/>')
        for ms, recall in coordinates:
            px, py = x(ms), y(recall)
            if marker == "diamond":
                parts.append(f'<path d="M {px:.2f} {py-4:.2f} L {px+4:.2f} {py:.2f} L {px:.2f} {py+4:.2f} L {px-4:.2f} {py:.2f} Z" fill="white" stroke="{color}" stroke-width="1.5"/>')
            else:
                parts.append(f'<circle cx="{px:.2f}" cy="{py:.2f}" r="3.5" fill="white" stroke="{color}" stroke-width="1.5"/>')
    for index, (_, label, color, dash, marker) in enumerate(CONFIGS):
        lx = 110 + (index % 2) * 270
        ly = 545 + (index // 2) * 23
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        parts.append(f'<line x1="{lx}" y1="{ly}" x2="{lx+28}" y2="{ly}" stroke="{color}" stroke-width="2"{dash_attr}/>')
        if marker == "diamond":
            parts.append(f'<path d="M {lx+14} {ly-4} l 4 4 -4 4 -4 -4 Z" fill="white" stroke="{color}" stroke-width="1.5"/>')
        else:
            parts.append(f'<circle cx="{lx+14}" cy="{ly}" r="3.5" fill="white" stroke="{color}" stroke-width="1.5"/>')
        parts.append(f'<text x="{lx+37}" y="{ly+4}" font-size="12">{escape(label)}</text>')
    parts.append('</g></svg>')
    output_dir = run_dir / "plots"
    output_dir.mkdir(exist_ok=True)
    output = output_dir / "recall_latency_four_configs.svg"
    output.write_text("\n".join(parts) + "\n")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    print(render(parser.parse_args().run_dir))
