#!/usr/bin/env bash
# Build and search one HNSW and one SHG index on Enron.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../../.."
profiler=build/profiling/hnsw_profile
data=experiments/profiling/data
indexes=experiments/profiling/indexes/enron
results=experiments/profiling/results/enron_example
observations=experiments/profiling/observations/enron_example

for algorithm in hnsw shg; do
  index="$indexes/enron_${algorithm}_example.index"
  if [[ ! -f $index ]]; then
    "$profiler" --algorithm "$algorithm" --dataset enron --build-only \
      --data-root "$data" --M 48 --ef-construction 80 --seed 100 \
      --index-file "$index" --performance-output "$observations/${algorithm}_build.csv"
  fi
  "$profiler" --algorithm "$algorithm" --dataset enron --search-only \
    --data-root "$data" --M 48 --ef-construction 80 --k 20 --ef-search 64 \
    --index-file "$index" --output "$results/${algorithm}_queries.csv" \
    --performance-output "$observations/${algorithm}_search.csv" \
    --layer-averages-output "$observations/${algorithm}_layers.csv"
done
