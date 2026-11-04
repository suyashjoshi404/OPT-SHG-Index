#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
optimization=O3
build_dir="$repo_root/build/profiling"
jobs=2
native=ON

usage() {
  cat <<'EOF'
Usage: build_profiler.sh [--optimization O3|Ofast] [--build-dir DIR] [--jobs N] [--native on|off]

Configure and build the HNSW/SHG profiler. The default is O3 in
build/profiling. Use separate build directories to keep both binaries.
Relative build directories are resolved from the repository root.
EOF
}

die() { printf 'Error: %s\n' "$*" >&2; exit 2; }
while (($#)); do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --optimization|--build-dir|--jobs|--native)
      (($# >= 2)) || die "Missing value for $1"
      case "$1" in
        --optimization) optimization=$2 ;;
        --build-dir) build_dir=$2 ;;
        --jobs) jobs=$2 ;;
        --native)
          case "$2" in
            on) native=ON ;;
            off) native=OFF ;;
            *) die "--native must be on or off" ;;
          esac ;;
      esac
      shift 2 ;;
    *) die "Unknown option: $1" ;;
  esac
done

[[ $optimization == O3 || $optimization == Ofast ]] || die "--optimization must be O3 or Ofast"
[[ $jobs =~ ^[1-9][0-9]*$ ]] || die "--jobs must be a positive integer"
[[ $build_dir = /* ]] || build_dir="$repo_root/$build_dir"

cmake -S "$repo_root/experiments/profiling" -B "$build_dir" \
  -DCMAKE_BUILD_TYPE=Release \
  -DPROFILING_OPTIMIZATION="$optimization" \
  -DPROFILING_NATIVE="$native"
cmake --build "$build_dir" --target hnsw_profile --parallel "$jobs"
printf 'Profiler (%s): %s/hnsw_profile\n' "$optimization" "$build_dir"
