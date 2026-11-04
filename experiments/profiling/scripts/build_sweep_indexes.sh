#!/usr/bin/env bash
# Build one HNSW and one SHG index per dataset; reuse complete saved indexes.
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
cd "$repo_root"
data_root=experiments/profiling/data
index_root=experiments/profiling/indexes
executable=build/profiling/hnsw_profile
datasets=(sift enron gist)
M=48
ef_construction=80
seed=100
force=false

usage() {
  cat <<'EOF'
Usage: build_sweep_indexes.sh [options]
  --datasets "sift enron gist"  Datasets to build (default: all three)
  --M N                         Graph degree (default: 48)
  --ef-construction N           Construction breadth (default: 80)
  --seed N                      Build seed (default: 100)
  --data-root DIR               Directory containing dataset subdirectories
  --index-root DIR              Directory for saved indexes
  --executable FILE             Native profiler binary
  --force                       Rebuild indexes even when saved files exist

Run from any directory. Relative paths are resolved from the repository root.
Complete indexes are reused unless --force is given.
EOF
}

die() { printf 'Error: %s\n' "$*" >&2; exit 2; }
while (($#)); do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --force) force=true; shift ;;
    --datasets|--M|--ef-construction|--seed|--data-root|--index-root|--executable)
      (($# >= 2)) || die "Missing value for $1"
      case "$1" in
        --datasets) read -r -a datasets <<< "$2" ;;
        --M) M=$2 ;;
        --ef-construction) ef_construction=$2 ;;
        --seed) seed=$2 ;;
        --data-root) data_root=$2 ;;
        --index-root) index_root=$2 ;;
        --executable) executable=$2 ;;
      esac
      shift 2 ;;
    *) die "Unknown option: $1" ;;
  esac
done

((${#datasets[@]})) || die "Select at least one dataset"
[[ $M =~ ^[0-9]+$ && $M -ge 2 ]] || die "--M must be at least 2"
[[ $ef_construction =~ ^[0-9]+$ && $ef_construction -ge 1 ]] || die "--ef-construction must be positive"
[[ $seed =~ ^[0-9]+$ ]] || die "--seed must be a nonnegative integer"
if [[ " ${datasets[*]} " == *" gist "* ]]; then
  [[ -f $executable ]] || die "Missing profiler binary: $executable; build it as described in README.md"
  profiler_help=$("$executable" --help 2>&1) || die "Cannot run profiler binary: $executable"
  [[ $profiler_help == *'--dataset sift|enron|gist'* ]] ||
    die "Profiler binary lacks GIST support: $executable. Rebuild it with: cmake --build build/profiling --target hnsw_profile -j2"
fi
for dataset in "${datasets[@]}"; do
  case "$dataset" in sift|enron|gist) ;; *) die "Unknown dataset: $dataset" ;; esac
  for algorithm in hnsw shg; do
    index_file="$index_root/$dataset/${dataset}_${algorithm}_sweep_M${M}_efc${ef_construction}_seed${seed}.index"
    if ! $force && [[ -f $index_file ]] && { [[ $algorithm == hnsw ]] || [[ -f $index_file.shg ]]; }; then
      printf 'Saved index: %s (use --force to rebuild)\n' "$index_file"
      continue
    fi
    if ! $force && [[ -e $index_file || -e $index_file.shg ]]; then
      die "Incomplete index at $index_file; use --force to rebuild"
    fi
    force_args=()
    if $force; then force_args=(--force); fi
    printf 'Building %s %s -> %s\n' "$dataset" "$algorithm" "$index_file"
    "$executable" --algorithm "$algorithm" --build-only \
      --dataset "$dataset" --data-root "$data_root" \
      --M "$M" --ef-construction "$ef_construction" --seed "$seed" \
      --index-file "$index_file" \
      --performance-output "${index_file%.index}_build.csv" "${force_args[@]}"
  done
done
