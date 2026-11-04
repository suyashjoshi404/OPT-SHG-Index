#!/usr/bin/env python3
"""Plot sweep comparisons from the saved summary CSV files."""

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


RUN = Path(__file__).resolve().parents[1] / "observations_v2/ef_search_sweep/run_1"
DATASETS = (("sift", "SIFT1M"), ("enron", "Enron"), ("gist", "GIST1M"))
SERIES = (
    ("hnsw_vanilla", "Vanilla HNSW", "#333333", "D", "-"),
    ("shg_vanilla", "Vanilla SHG", "#e53935", "o", "--"),
    ("hnsw_pf_filter", "HNSW with PF Filter", "#1f77b4", "D", "-"),
    ("shg_pf_filter", "SHG with PF Filter", "#1fb662", "o", "-"),
)


def save(fig, name):
    stem = RUN / "plots" / name
    for extension in ("png", "svg"):
        fig.savefig(stem.with_suffix(f".{extension}"), dpi=220)
    plt.close(fig)


def plot_lines(chart, variant):
    with (RUN / "plots/sweep_summary.csv").open(newline="") as source:
        rows = list(csv.DictReader(source))
    series = SERIES[:2] if variant == "vanilla" else SERIES
    name = ("recall_latency_vanilla_all_datasets" if variant == "vanilla"
            else f"{chart}_all_datasets")

    fig, axes = plt.subplots(1, 3, figsize=(15.8, 4.74))
    handles = []
    for ax, (dataset, title) in zip(axes, DATASETS):
        for config, label, color, marker, linestyle in series:
            points = sorted(
                (row for row in rows if row["dataset"] == dataset and row["configuration"] == config),
                key=lambda row: int(row["ef_search"]),
            )
            if not points:
                raise ValueError(f"Missing {dataset}/{config} in sweep summary")
            line, = ax.plot(
                ([float(row["mean_latency_ms"]) for row in points] if chart == "recall_latency"
                 else range(len(points))),
                [float(row["mean_recall_at_k"] if chart == "recall_latency" else row["mean_qps"])
                 for row in points],
                color=color, marker=marker, linestyle=linestyle, linewidth=1.3,
                markersize=5.5, markerfacecolor="white", markeredgewidth=1.1,
                label=label,
            )
            if dataset == DATASETS[0][0]:
                handles.append(line)
        if chart == "qps":
            ax.set_xticks(range(len(points)), [row["ef_search"] for row in points], rotation=45)
        ax.set(title=title, xlabel="Mean latency (ms)" if chart == "recall_latency" else "efSearch",
               ylabel="Recall@20" if chart == "recall_latency" else "Queries per second (QPS)")
        ax.grid(alpha=0.2)

    fig.subplots_adjust(left=0.05, right=0.99, top=0.88,
                        bottom=0.31 if chart == "qps" else 0.23, wspace=0.22)
    fig.legend(handles=handles, loc="lower center", ncol=len(series), frameon=False,
               bbox_to_anchor=(0.5, 0.02 if chart == "qps" else 0.055), fontsize=13)
    save(fig, name)


def plot_speedup():
    with (RUN / "plots/mean_latency_speedup.csv").open(newline="") as source:
        rows = list(csv.DictReader(source))
    values = {(row["dataset"], row["configuration"]): float(row["mean_speedup_x"])
              for row in rows}
    fig, ax = plt.subplots(figsize=(10.9, 4.83))
    positions = range(len(DATASETS))
    width = 0.16
    for index, (config, label, color, _, _) in enumerate(SERIES):
        x = [position + (index - 1.5) * width for position in positions]
        heights = [values[dataset, config] for dataset, _ in DATASETS]
        bars = ax.bar(x, heights, width=width, color=color, label=label)
        for bar, height in zip(bars, heights):
            ax.text(bar.get_x() + bar.get_width() / 2, height + 0.035,
                    f"{height:.2f}×", ha="center", va="bottom", fontsize=9)
    ax.axhline(1, color="#888888", linestyle="--", linewidth=1)
    ax.set_xticks(list(positions), [title for _, title in DATASETS])
    ax.set_ylabel("Mean latency speedup vs HNSW native (×)")
    ax.set_ylim(0, 2.75)
    ax.grid(axis="y", alpha=0.2)
    ax.set_axisbelow(True)
    fig.subplots_adjust(left=0.08, right=0.99, top=0.92, bottom=0.22)
    fig.legend(loc="lower center", ncol=4, frameon=False,
               bbox_to_anchor=(0.5, 0.035), fontsize=12)
    save(fig, "mean_latency_speedup_all_datasets")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chart", choices=("recall_latency", "qps", "speedup"),
                        default="recall_latency")
    parser.add_argument("--variant", choices=("vanilla", "all"), default="all")
    args = parser.parse_args()
    if args.chart != "recall_latency" and args.variant == "vanilla":
        parser.error("--variant vanilla is only supported for recall_latency")
    plt.rcParams.update({"font.size": 10, "axes.titlesize": 12, "axes.titleweight": "bold"})
    if args.chart == "speedup":
        plot_speedup()
    else:
        plot_lines(args.chart, args.variant)


if __name__ == "__main__":
    main()
