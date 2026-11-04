#!/usr/bin/env bash
# Search saved indexes across efSearch values and prefetch/pruning modes.
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
cd "$repo_root"
script_dir=experiments/profiling/scripts
data_root=experiments/profiling/data
index_root=experiments/profiling/indexes
results_base=experiments/profiling/results/ef_search_sweep
observations_base=experiments/profiling/observations/ef_search_sweep
executable=build/profiling/hnsw_profile
run_id=
datasets=(sift enron gist)
configs=(hnsw_off hnsw_native shg_baseline shg_lookahead shg_noprune)
ef_values=(20 24 32 48 64 96 128 192 256 512)
M=48
ef_construction=80
seed=100
k=20
repeats=5
warmup=500

usage() {
  cat <<'EOF'
Usage: run_ef_search_sweep.sh [options]
  --datasets "sift enron gist"  Datasets to search (default: all three)
  --configs "..."               Space-separated configurations (default: all five)
  --ef-values "20 24 32 ..."   Space-separated efSearch values
  --repeats N                   Searches per point (default: 5)
  --k N                         Neighbors requested (default: 20)
  --warmup N                    Warm-up queries (default: 500)
  --M N                         Saved index M (default: 48)
  --ef-construction N           Saved index construction breadth (default: 80)
  --seed N                      Saved index build seed (default: 100)
  --data-root DIR               Directory containing dataset subdirectories
  --index-root DIR              Directory containing saved indexes
  --results-base DIR            Parent for per-query result run directories
  --observations-base DIR       Parent for performance observation run directories
  --run-id run_N                Use a specific unused run number (default: next number)
  --executable FILE             Native profiler binary

Run build_sweep_indexes.sh first with matching dataset, M, construction breadth,
seed, and index root. Relative paths are resolved from the repository root.
EOF
}

die() { printf 'Error: %s\n' "$*" >&2; exit 2; }
while (($#)); do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --datasets|--configs|--ef-values|--repeats|--k|--warmup|--M|--ef-construction|--seed|--data-root|--index-root|--results-base|--observations-base|--run-id|--executable)
      (($# >= 2)) || die "Missing value for $1"
      case "$1" in
        --datasets) read -r -a datasets <<< "$2" ;;
        --configs) read -r -a configs <<< "$2" ;;
        --ef-values) read -r -a ef_values <<< "$2" ;;
        --repeats) repeats=$2 ;;
        --k) k=$2 ;;
        --warmup) warmup=$2 ;;
        --M) M=$2 ;;
        --ef-construction) ef_construction=$2 ;;
        --seed) seed=$2 ;;
        --data-root) data_root=$2 ;;
        --index-root) index_root=$2 ;;
        --results-base) results_base=$2 ;;
        --observations-base) observations_base=$2 ;;
        --run-id) run_id=$2 ;;
        --executable) executable=$2 ;;
      esac
      shift 2 ;;
    *) die "Unknown option: $1" ;;
  esac
done

((${#datasets[@]} && ${#configs[@]} && ${#ef_values[@]})) || die "Datasets, configs, and ef values cannot be empty"
[[ $M =~ ^[0-9]+$ && $M -ge 2 ]] || die "--M must be at least 2"
[[ $ef_construction =~ ^[0-9]+$ && $ef_construction -ge 1 ]] || die "--ef-construction must be positive"
[[ $seed =~ ^[0-9]+$ ]] || die "--seed must be a nonnegative integer"
[[ $k =~ ^[0-9]+$ && $k -ge 1 ]] || die "--k must be positive"
[[ $repeats =~ ^[0-9]+$ && $repeats -ge 1 ]] || die "--repeats must be positive"
[[ $warmup =~ ^[0-9]+$ ]] || die "--warmup must be a nonnegative integer"
if [[ -n $run_id && ! $run_id =~ ^run_[1-9][0-9]*$ ]]; then
  die "--run-id must have the form run_N, starting at run_1"
fi
for dataset in "${datasets[@]}"; do
  case "$dataset" in sift|enron|gist) ;; *) die "Unknown dataset: $dataset" ;; esac
done
for config in "${configs[@]}"; do
  case "$config" in
    hnsw_off|hnsw_native|hnsw_v2_filter|shg_baseline|shg_lookahead|shg_noprune|shg_v2_filter) ;;
    *) die "Unknown configuration: $config" ;;
  esac
done
for ef in "${ef_values[@]}"; do
  [[ $ef =~ ^[0-9]+$ && $ef -ge $k ]] || die "Each efSearch must be an integer at least k=$k"
done

[[ -f $executable ]] || die "Missing profiler binary: $executable; build it as described in experiments/profiling/README.md"
if [[ " ${datasets[*]} " == *" gist "* ]]; then
  profiler_help=$("$executable" --help 2>&1) || die "Cannot run profiler binary: $executable"
  [[ $profiler_help == *'--dataset sift|enron|gist'* ]] ||
    die "Profiler binary lacks GIST support: $executable. Rebuild it with: cmake --build build/profiling --target hnsw_profile -j2"
fi
for dataset in "${datasets[@]}"; do
  for config in "${configs[@]}"; do
    algorithm=${config%%_*}
    index_file="$index_root/$dataset/${dataset}_${algorithm}_sweep_M${M}_efc${ef_construction}_seed${seed}.index"
    [[ -f $index_file ]] || die "Missing index: $index_file; run build_sweep_indexes.sh first"
    if [[ $algorithm == shg ]]; then
      [[ -f $index_file.shg ]] || die "Missing SHG companion: $index_file.shg"
    fi
  done
done

if [[ -z $run_id ]]; then
  latest=0
  for path in "$results_base"/run_* "$observations_base"/run_*; do
    [[ -e $path ]] || continue
    name=${path##*/}
    if [[ $name =~ ^run_([1-9][0-9]*)$ ]] && ((10#${BASH_REMATCH[1]} > latest)); then
      latest=$((10#${BASH_REMATCH[1]}))
    fi
  done
  run_id="run_$((latest + 1))"
fi
results_root="$results_base/$run_id"
observations_root="$observations_base/$run_id"
[[ ! -e $results_root && ! -e $observations_root ]] || die "Run ID already exists: $run_id"

mkdir -p "$results_root" "$observations_root"
for dataset in "${datasets[@]}"; do
  for config in "${configs[@]}"; do
    algorithm=${config%%_*}
    case "$config" in
      hnsw_off) mode=off; pruning_args=() ;;
      hnsw_native) mode=native; pruning_args=() ;;
      hnsw_v2_filter) mode=v2_filter; pruning_args=() ;;
      shg_baseline) mode=baseline; pruning_args=(--base-pruning on) ;;
      shg_lookahead) mode=lookahead; pruning_args=(--base-pruning on) ;;
      shg_noprune) mode=baseline; pruning_args=(--base-pruning off) ;;
      shg_v2_filter) mode=v2_filter; pruning_args=(--base-pruning on) ;;
    esac
    index_file="$index_root/$dataset/${dataset}_${algorithm}_sweep_M${M}_efc${ef_construction}_seed${seed}.index"
    for ef in "${ef_values[@]}"; do
      result_dir="$results_root/$dataset/$config/M${M}_efc${ef_construction}_ef${ef}_k${k}"
      observation_dir="$observations_root/$dataset/$config/ef${ef}_k${k}"
      mkdir -p "$result_dir" "$observation_dir"
      for ((repeat=1; repeat<=repeats; repeat++)); do
        printf '%s %s efSearch=%s repeat=%s/%s\n' "$dataset" "$config" "$ef" "$repeat" "$repeats"
        python3 "$script_dir/profile_${algorithm}_query.py" \
          --dataset "$dataset" --data-root "$data_root" \
          --M "$M" --ef-construction "$ef_construction" \
          --k "$k" --ef-search "$ef" --threads 1 --warmup "$warmup" \
          --prefetch-mode "$mode" "${pruning_args[@]}" \
          --index-file "$index_file" --executable "$executable" \
          --output "$result_dir/repeat${repeat}_layer_stats.csv" \
          --performance-output "$observation_dir/repeat${repeat}_performance.csv" \
          --layer-averages-output "$observation_dir/repeat${repeat}_layer_averages.csv"
      done
    done
  done
done
printf 'Results: %s\nObservations: %s\n' "$results_root" "$observations_root"
