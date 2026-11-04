#!/usr/bin/env python3
"""Plot full-query-set recall against mean latency across efSearch repeats."""

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path
from statistics import fmean, stdev


def summarize(run_dir, selected_configs=None):
    measurements = defaultdict(list)
    for path in sorted(run_dir.glob("*/*/ef*_k*/repeat*_performance.csv")):
        dataset, configuration = path.relative_to(run_dir).parts[:2]
        if selected_configs is not None and configuration not in selected_configs:
            continue
        with path.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        if len(rows) != 1 or rows[0]["phase"] != "search":
            raise ValueError(f"Expected exactly one search row in {path}")
        row = rows[0]
        if (int(row["M"]), int(row["ef_construction"]), int(row["k"]),
                int(row["threads"])) != (48, 80, 20, 1):
            raise ValueError(f"Expected M48/efC80/k20/threads1 in {path}")
        if row["dataset"] != dataset or row["algorithm"] != configuration.split("_", 1)[0]:
            raise ValueError(f"Dataset or algorithm does not match directory in {path}")
        key = dataset, configuration, int(row["ef_search"])
        measurements[key].append(row)
    datasets = {key[0] for key in measurements}
    configurations = {key[1] for key in measurements}
    if not datasets or not datasets <= {"sift", "enron", "gist"}:
        raise ValueError(f"Unexpected datasets: {datasets}")
    legacy = {"hnsw", "shg"}
    four_modes = {"hnsw_off", "hnsw_native", "shg_baseline", "shg_lookahead"}
    five_modes = four_modes | {"shg_noprune"}
    if selected_configs is not None:
        if configurations != selected_configs:
            raise ValueError(f"Missing selected configurations: {selected_configs - configurations}")
    elif configurations not in (legacy, four_modes, five_modes):
        raise ValueError(f"Expected legacy, four-mode, or five-mode sweep, found {configurations}")
    expected = {(dataset, configuration, ef)
                for dataset in datasets for configuration in configurations
                for ef in (20, 24, 32, 48, 64, 96, 128, 192, 256, 512)}
    if set(measurements) != expected:
        raise ValueError(f"Incomplete or unexpected sweep: missing {expected - set(measurements)}, "
                         f"extra {set(measurements) - expected}")
    summary = []
    for (dataset, configuration, ef), rows in sorted(measurements.items()):
        if len(rows) != 5:
            raise ValueError(f"Expected five repeats for {dataset}/{configuration}/ef{ef}")
        count = {"sift": 10000, "enron": 200, "gist": 1000}[dataset]
        if {int(r["count"]) for r in rows} != {count}:
            raise ValueError(f"Unexpected query count for {dataset}/{configuration}/ef{ef}")
        recalls = [float(r["recall_at_k"]) for r in rows]
        if not all(math.isclose(r, recalls[0], abs_tol=1e-8) for r in recalls):
            raise ValueError(f"Recall differs between repeats for {dataset}/{configuration}/ef{ef}")
        latencies = [float(r["average_latency_us"]) / 1000 for r in rows]
        qps = [float(r["queries_per_second"]) for r in rows]
        if not all(math.isfinite(t) and t > 0 for t in latencies + qps):
            raise ValueError("Latency and QPS must be finite and positive")
        summary.append(dict(dataset=dataset, configuration=configuration,
                            algorithm=rows[0]["algorithm"],
                            prefetch_mode=("baseline" if configuration == "shg_noprune" else
                                           configuration.split("_", 1)[1] if "_" in configuration else ""),
                            base_pruning="off" if configuration == "shg_noprune" else "on",
                            M=48,
                            ef_construction=80, k=20, ef_search=ef, repeats=5,
                            query_count=count, mean_recall_at_k=fmean(recalls),
                            mean_latency_ms=fmean(latencies),
                            mean_qps=fmean(qps),
                            std_latency_ms=stdev(latencies),
                            min_latency_ms=min(latencies), max_latency_ms=max(latencies)))
    if configurations in (four_modes, five_modes) or selected_configs is not None:
        by_key = {(row["dataset"], row["configuration"], row["ef_search"]): row
                  for row in summary}
        for dataset in datasets:
            for ef in (20, 24, 32, 48, 64, 96, 128, 192, 256, 512):
                for first, second in (("hnsw_off", "hnsw_native"),
                                      ("shg_baseline", "shg_lookahead")):
                    if first not in configurations or second not in configurations:
                        continue
                    left = by_key[dataset, first, ef]["mean_recall_at_k"]
                    right = by_key[dataset, second, ef]["mean_recall_at_k"]
                    if not math.isclose(left, right, rel_tol=0, abs_tol=1e-8):
                        raise ValueError(f"Prefetch modes differ in recall: {dataset}/ef{ef}/{first}/{second}")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path, help="Observation directory for one complete sweep")
    parser.add_argument("--configs", nargs="+", help="Plot only these configurations")
    parser.add_argument("--chart", choices=("all", "recall_latency", "qps", "mean_latency"),
                        default="all", help="Render one chart or the full set")
    parser.add_argument("--output-stem", help="Filename stem when rendering one chart")
    args = parser.parse_args()
    if args.output_stem and args.chart == "all":
        parser.error("--output-stem requires a single --chart")
    selected_configs = set(args.configs) if args.configs else None
    known_configs = {"hnsw_off", "hnsw_native", "hnsw_v2_filter", "shg_baseline",
                     "shg_lookahead", "shg_noprune", "shg_v2_filter"}
    if selected_configs is not None and not selected_configs <= known_configs:
        parser.error(f"Unknown configurations: {sorted(selected_configs - known_configs)}")
    summary = summarize(args.run_dir, selected_configs)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.linewidth": 0.6, "axes.edgecolor": "0.5",
                         "xtick.direction": "in", "ytick.direction": "in",
                         "pdf.fonttype": 42})
    configurations = {row["configuration"] for row in summary}
    styles = (("hnsw_off", "HNSW, hints off", "#333333", "D", "--"),
              ("hnsw_native", "HNSW, native hints", "#333333", "D", "-"),
              ("shg_baseline", "SHG, baseline", "#c62828", "o", "--"),
              ("shg_lookahead", "SHG, lookahead", "#c62828", "o", "-"),
              ("shg_noprune", "SHG, no base pruning", "#d97706", "^", ":"),
              ("hnsw_v2_filter", "HNSW with PF Filter", "#2471a3", "D", "-"),
              ("shg_v2_filter", "SHG with PF Filter", "#27ae60", "o", "-"))
    if selected_configs == {"hnsw_native", "shg_baseline", "hnsw_v2_filter", "shg_v2_filter"}:
        styles = tuple((config, {"hnsw_native": "Vanilla HNSW", "shg_baseline": "Vanilla SHG"}.get(config, label),
                        color, marker, linestyle)
                       for config, label, color, marker, linestyle in styles)
    if selected_configs == {"hnsw_native", "shg_baseline"}:
        styles = tuple((config, {"hnsw_native": "Vanilla HNSW", "shg_baseline": "Vanilla SHG"}.get(config, label),
                        color, marker, linestyle)
                       for config, label, color, marker, linestyle in styles)
    if configurations == {"hnsw", "shg"}:
        styles = (("hnsw", "HNSW", "black", "D", "-"),
                  ("shg", "SHG", "red", "o", "-."))
    datasets = [dataset for dataset in ("sift", "enron", "gist")
                if any(row["dataset"] == dataset for row in summary)]
    names = {"sift": "SIFT1M", "enron": "Enron", "gist": "GIST1M"}
    by_key = defaultdict(list)
    for row in summary:
        by_key[row["dataset"], row["configuration"]].append(row)
    for points in by_key.values():
        points.sort(key=lambda row: row["ef_search"])
    ef_values = sorted({row["ef_search"] for row in summary})
    charts = (("recall_latency", "Recall versus mean latency", "Mean latency (ms)", "Recall@20"),
              ("qps", "Search throughput by efSearch", "efSearch", "Queries per second (QPS)"),
              ("mean_latency", "Mean query latency by efSearch", "efSearch", "Mean latency per query (ms)"))
    if args.chart != "all":
        charts = tuple(chart for chart in charts if chart[0] == args.chart)
    output_dir = args.run_dir / "plots"
    output_dir.mkdir(parents=True, exist_ok=True)
    for chart_name, title, xlabel, ylabel in charts:
        fig, axes = plt.subplots(1, len(datasets), figsize=(5.3 * len(datasets), 4.7), squeeze=False)
        for index, dataset in enumerate(datasets):
            ax = axes[0, index]
            for configuration, label, color, marker, linestyle in styles:
                if configuration not in configurations:
                    continue
                points = by_key[dataset, configuration]
                if chart_name == "recall_latency":
                    x = [r["mean_latency_ms"] for r in points]
                    y = [r["mean_recall_at_k"] for r in points]
                else:
                    x = list(range(len(points)))
                    field = "mean_qps" if chart_name == "qps" else "mean_latency_ms"
                    y = [r[field] for r in points]
                ax.plot(x, y, color=color, marker=marker, markerfacecolor="white",
                        markersize=5, markeredgewidth=1, linestyle=linestyle,
                        linewidth=1.3, label=label)
            if chart_name == "recall_latency":
                lowest = min(r["mean_recall_at_k"] for r in summary if r["dataset"] == dataset)
                ax.set_ylim(max(0, lowest - 0.04), 1.01)
            else:
                ax.set_xticks(range(len(ef_values)), [str(ef) for ef in ef_values], rotation=45)
                ax.set_ylim(bottom=0)
            ax.set_xlabel(xlabel)
            ax.set_ylabel(ylabel)
            ax.set_title(names[dataset], fontweight="bold", pad=10)
            ax.grid(alpha=0.2)
        fig.suptitle(f"{title} (M=48, efC=80, k=20)", fontsize=14, fontweight="bold")
        handles, labels = axes[0, 0].get_legend_handles_labels()
        fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, 0.065),
                   ncol=len(labels), frameon=False, fontsize=9)
        fig.text(0.5, 0.02, "Each point is the mean of five complete-query-set searches.",
                 ha="center", fontsize=9)
        fig.tight_layout(rect=(0, 0.13, 1, 0.92), w_pad=2)
        stem = output_dir / (args.output_stem or f"{chart_name}_all_datasets")
        for extension in ("png", "pdf", "svg"):
            path = stem.with_suffix("." + extension)
            fig.savefig(path, dpi=220, bbox_inches="tight", facecolor="white")
            print(path)
        plt.close(fig)
    if args.chart != "all":
        print(f"Validated {len(summary)} sweep points from {len(summary) * 5} search measurements.")
        return
    summary_path = output_dir / "sweep_summary.csv"
    with summary_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)
    print(summary_path)

    if "hnsw_native" in configurations:
        speedups = []
        for dataset in datasets:
            baseline = {row["ef_search"]: row["mean_latency_ms"]
                        for row in by_key[dataset, "hnsw_native"]}
            for configuration, *_ in styles:
                if configuration not in configurations:
                    continue
                for row in by_key[dataset, configuration]:
                    speedups.append(dict(dataset=dataset, configuration=configuration,
                                         ef_search=row["ef_search"],
                                         baseline_mean_latency_ms=baseline[row["ef_search"]],
                                         configuration_mean_latency_ms=row["mean_latency_ms"],
                                         speedup_x=baseline[row["ef_search"]] / row["mean_latency_ms"]))
        speedup_path = output_dir / "latency_speedup_by_ef_search.csv"
        with speedup_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(speedups[0]))
            writer.writeheader()
            writer.writerows(speedups)
        print(speedup_path)

        fig, axes = plt.subplots(1, len(datasets), figsize=(5.3 * len(datasets), 4.7), squeeze=False)
        for index, dataset in enumerate(datasets):
            ax = axes[0, index]
            for configuration, label, color, marker, linestyle in styles:
                if configuration not in configurations:
                    continue
                points = [row for row in speedups if row["dataset"] == dataset
                          and row["configuration"] == configuration]
                ax.plot(range(len(points)), [row["speedup_x"] for row in points],
                        color=color, marker=marker, markerfacecolor="white",
                        markersize=5, markeredgewidth=1, linestyle=linestyle,
                        linewidth=1.3, label=label)
            ax.axhline(1, color="#777777", linewidth=0.7, zorder=0)
            ax.set_xticks(range(len(ef_values)), [str(ef) for ef in ef_values], rotation=45)
            ax.set_xlabel("efSearch")
            ax.set_ylabel("Latency speedup vs HNSW native (×)")
            ax.set_title(names[dataset], fontweight="bold", pad=10)
            ax.set_ylim(bottom=0)
            ax.grid(alpha=0.2)
        fig.suptitle("Mean query latency speedup by efSearch", fontsize=14, fontweight="bold")
        handles, labels = axes[0, 0].get_legend_handles_labels()
        fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, 0.065),
                   ncol=len(labels), frameon=False, fontsize=9)
        fig.text(0.5, 0.02, "HNSW native mean latency / configuration mean latency at the same efSearch; recall may differ.",
                 ha="center", fontsize=9)
        fig.tight_layout(rect=(0, 0.13, 1, 0.92), w_pad=2)
        for extension in ("png", "pdf", "svg"):
            path = output_dir / f"latency_speedup_by_ef_search_all_datasets.{extension}"
            fig.savefig(path, dpi=220, bbox_inches="tight", facecolor="white")
            print(path)
        plt.close(fig)

        averages = []
        for dataset in datasets:
            for configuration, *_ in styles:
                if configuration not in configurations:
                    continue
                values = [row["speedup_x"] for row in speedups
                          if row["dataset"] == dataset and row["configuration"] == configuration]
                averages.append(dict(dataset=dataset, configuration=configuration,
                                     ef_search_points=len(values), mean_speedup_x=fmean(values)))
        average_path = output_dir / "mean_latency_speedup.csv"
        with average_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(averages[0]))
            writer.writeheader()
            writer.writerows(averages)
        print(average_path)

        fig, ax = plt.subplots(figsize=(11, 4.8))
        visible_styles = [style for style in styles if style[0] in configurations]
        bar_width = 0.15
        bar_colors = {"hnsw_off": "#8c8c8c", "hnsw_native": "#333333",
                      "shg_baseline": "#c62828", "shg_lookahead": "#ef7777",
                      "shg_noprune": "#d97706", "hnsw_v2_filter": "#2471a3",
                      "shg_v2_filter": "#27ae60"}
        for style_index, (configuration, label, _, _, _) in enumerate(visible_styles):
            positions = [index + (style_index - (len(visible_styles) - 1) / 2) * bar_width
                         for index in range(len(datasets))]
            values = [next(row["mean_speedup_x"] for row in averages
                           if row["dataset"] == dataset and row["configuration"] == configuration)
                      for dataset in datasets]
            bars = ax.bar(positions, values, width=bar_width, label=label,
                          color=bar_colors[configuration], edgecolor="white", linewidth=0.5)
            ax.bar_label(bars, fmt="%.2f×", padding=3, fontsize=8)
        ax.axhline(1, color="#777777", linewidth=0.8, linestyle="--", zorder=0)
        ax.set_xticks(range(len(datasets)), [names[dataset] for dataset in datasets])
        ax.set_ylabel("Mean latency speedup vs HNSW native (×)")
        ax.set_ylim(bottom=0)
        ax.grid(axis="y", alpha=0.2)
        ax.set_axisbelow(True)
        fig.suptitle("Mean latency speedup across efSearch values", fontsize=14, fontweight="bold")
        fig.legend(loc="lower center", bbox_to_anchor=(0.5, 0.065),
                   ncol=len(visible_styles), frameon=False, fontsize=9)
        fig.text(0.5, 0.02, "Arithmetic mean of same-efSearch latency ratios over ten values; recall may differ.",
                 ha="center", fontsize=9)
        fig.tight_layout(rect=(0, 0.13, 1, 0.92))
        for extension in ("png", "pdf", "svg"):
            path = output_dir / f"mean_latency_speedup_all_datasets.{extension}"
            fig.savefig(path, dpi=220, bbox_inches="tight", facecolor="white")
            print(path)
        plt.close(fig)
    print(f"Validated {len(summary)} sweep points from {len(summary) * 5} search measurements.")


if __name__ == "__main__":
    main()
