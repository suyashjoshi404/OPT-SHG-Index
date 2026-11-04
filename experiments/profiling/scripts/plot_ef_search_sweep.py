#!/usr/bin/env python3
"""Plot recall versus latency and QPS from an efSearch sweep."""

import argparse
import csv
import math
import re
from collections import defaultdict
from pathlib import Path
from statistics import fmean


def summarize(run_dir, selected):
    measurements = defaultdict(dict)
    for path in sorted(run_dir.glob("*/*/ef*_k*/repeat*_performance.csv")):
        dataset, config, folder, filename = path.relative_to(run_dir).parts
        if selected and config not in selected:
            continue
        with path.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        if len(rows) != 1:
            raise ValueError(f"Expected one performance row: {path}")
        row = rows[0]
        ef, k = map(int, re.fullmatch(r"ef(\d+)_k(\d+)", folder).groups())
        repeat = int(re.fullmatch(r"repeat(\d+)_performance\.csv", filename).group(1))
        if (row["phase"] != "search" or row["dataset"] != dataset
                or row["algorithm"] != config.split("_", 1)[0]
                or int(row["ef_search"]) != ef or int(row["k"]) != k):
            raise ValueError(f"Performance row does not match its path: {path}")
        key = dataset, config, ef
        if repeat in measurements[key]:
            raise ValueError(f"Duplicate repeat: {path}")
        measurements[key][repeat] = row

    if not measurements:
        raise ValueError(f"No performance CSVs found in {run_dir}")
    configs = {config for _, config, _ in measurements}
    if selected and configs != selected:
        raise ValueError(f"Missing configurations: {selected - configs}")
    datasets = {dataset for dataset, _, _ in measurements}
    ef_values = {ef for _, _, ef in measurements}
    expected = {(dataset, config, ef) for dataset in datasets for config in configs for ef in ef_values}
    if set(measurements) != expected:
        raise ValueError(f"Incomplete sweep: {expected - set(measurements)}")
    repeat_sets = [set(repeats) for repeats in measurements.values()]
    if any(repeats != repeat_sets[0] for repeats in repeat_sets):
        raise ValueError("Repeat numbers differ across sweep points")

    summary = []
    for (dataset, config, ef), repeats in sorted(measurements.items()):
        rows = list(repeats.values())
        counts = {int(row["count"]) for row in rows}
        recalls = [float(row["recall_at_k"]) for row in rows]
        latencies = [float(row["average_latency_us"]) / 1000 for row in rows]
        qps = [float(row["queries_per_second"]) for row in rows]
        if (len(counts) != 1 or next(iter(counts)) <= 0
                or not all(math.isfinite(value) for value in recalls + latencies + qps)
                or not all(value > 0 for value in latencies + qps)
                or not all(math.isclose(value, recalls[0], abs_tol=1e-8) for value in recalls)):
            raise ValueError(f"Invalid or inconsistent measurements: {dataset}/{config}/ef{ef}")
        summary.append(dict(dataset=dataset, configuration=config, ef_search=ef,
                            repeats=len(rows), query_count=next(iter(counts)), recall_at_k=fmean(recalls),
                            mean_latency_ms=fmean(latencies), mean_qps=fmean(qps)))
    by_key = {(row["dataset"], row["configuration"], row["ef_search"]): row for row in summary}
    for dataset in datasets:
        for ef in ef_values:
            for left, right in (("hnsw_vanilla_pf_off", "hnsw_vanilla"),
                                ("shg_vanilla", "shg_prototype_v1")):
                if left in configs and right in configs:
                    if not math.isclose(by_key[dataset, left, ef]["recall_at_k"],
                                        by_key[dataset, right, ef]["recall_at_k"], abs_tol=1e-8):
                        raise ValueError(f"Prefetch modes differ in recall: {dataset}/ef{ef}")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path, help="Observation directory for one sweep run")
    parser.add_argument("--configs", nargs="+", help="Only plot these configurations")
    parser.add_argument("--chart", choices=("all", "recall_latency", "qps"), default="all")
    parser.add_argument("--output-stem", help="Output filename without extension, for a single chart")
    args = parser.parse_args()
    if args.output_stem and args.chart == "all":
        parser.error("--output-stem requires a single --chart")
    summary = summarize(args.run_dir, set(args.configs) if args.configs else None)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_dir = args.run_dir / "plots"
    output_dir.mkdir(parents=True, exist_ok=True)
    datasets = sorted({row["dataset"] for row in summary})
    configs = sorted({row["configuration"] for row in summary})
    points = defaultdict(list)
    for row in summary:
        points[row["dataset"], row["configuration"]].append(row)
    for rows in points.values():
        rows.sort(key=lambda row: row["ef_search"])

    charts = ("recall_latency", "qps") if args.chart == "all" else (args.chart,)
    for chart in charts:
        fig, axes = plt.subplots(1, len(datasets), figsize=(5 * len(datasets), 4), squeeze=False)
        for ax, dataset in zip(axes[0], datasets):
            for config in configs:
                rows = points[dataset, config]
                x = [row["mean_latency_ms"] if chart == "recall_latency" else row["ef_search"] for row in rows]
                y = [row["recall_at_k"] if chart == "recall_latency" else row["mean_qps"] for row in rows]
                ax.plot(x, y, marker="o", label=config.replace("_", " "))
            ax.set(title=dataset.upper(), xlabel="Mean latency (ms)" if chart == "recall_latency" else "efSearch",
                   ylabel="Recall@k" if chart == "recall_latency" else "Queries per second")
            ax.grid(alpha=0.25)
            ax.legend(fontsize=8)
        fig.tight_layout()
        path = output_dir / f"{args.output_stem or chart}.png"
        fig.savefig(path, dpi=180)
        plt.close(fig)
        print(path)

    if args.chart == "all":
        path = output_dir / "sweep_summary.csv"
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
            writer.writeheader()
            writer.writerows(summary)
        print(path)


if __name__ == "__main__":
    main()
