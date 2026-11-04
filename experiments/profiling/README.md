# Native HNSW and SHG profiling

This experiment builds and profiles SIFT1M, Enron, or GIST with native
`hnswlib::HierarchicalNSW<float>` (HNSW) and `hnswlib::HEDS<float>` (SHG).
HNSW can run with its existing search-time software prefetch hints enabled
(`native`) or disabled (`off`). SHG has its own shortcut-aware prefetch modes.
The same C++ driver runs both algorithms sequentially. Python scripts launch
it; FAISS and NumPy are not needed. Run all commands from the repository root.

## Build

You need a C++17 compiler, CMake 3.16+, and Python 3.8+. On Ubuntu/Debian:

```bash
sudo apt install build-essential cmake python3 numactl
```

```bash
bash experiments/profiling/scripts/build_profiler.sh --optimization O3
```

To compare compiler optimization modes while keeping both binaries:

```bash
bash experiments/profiling/scripts/build_profiler.sh --optimization O3 --build-dir build/profiling-o3
bash experiments/profiling/scripts/build_profiler.sh --optimization Ofast --build-dir build/profiling-ofast
```

Pass `--executable build/profiling-o3/hnsw_profile` or
`--executable build/profiling-ofast/hnsw_profile` to the Python build/search
scripts. Give search runs separate `--output`, `--performance-output`, and
`--layer-averages-output` paths so their results remain distinct. Without
`--build-dir`, the build script updates `build/profiling`.
It accepts `--jobs N` and `--native off` (disables `-march=native`). You can
also configure CMake directly with `-DPROFILING_OPTIMIZATION=O3` or `Ofast`.

The driver uses one thread. `O3` is the default; `Ofast` enables additional
optimizations including fast math. OpenMP is disabled in both modes, so
`Ofast` alone does not reproduce the root example's build settings. Rebuild
the binary after changing headers or the driver. Run
`ctest --test-dir build/profiling --output-on-failure` to check the driver with
small fixtures (the script builds only `hnsw_profile`; build the test targets
first with `cmake --build build/profiling`).

For a search-only comparison, reuse the same saved HNSW index or SHG
`.index`/`.index.shg` pair with both binaries. Changing optimization mode does
not require rebuilding indexes. Rebuild with each mode only if you also want
to compare index construction or the graphs it produces; fast math can change
floating-point decisions during construction.

## Prepare data

The default layout under `experiments/profiling/data/` is:

```text
sift/sift_base.fvecs
sift/sift_query.fvecs
sift/sift_groundtruth.ivecs
enron/enron.data_new
enron/enron_query.fvecs
enron/enron_groundtruth.ivecs
gist/gist_base.fvecs
gist/gist_query.fvecs
gist/gist_groundtruth.ivecs
```

The `data` directory may be a symlink. For another location, pass
`--data-root PATH` pointing to a directory containing `sift/`, `enron/`, or `gist/`.
Base vectors use fvecs (an `int32` dimension and float32 values per record)
or `data_new` (uint32 element byte size, vector count, and dimension, then
float32 values). Queries use fvecs; ground truth uses ivecs (record width and
uint32 zero-based IDs). Files must be little-endian on a little-endian host.

Check headers and file sizes before a large build:

```bash
build/profiling/hnsw_profile --check-data --dataset sift
build/profiling/hnsw_profile --check-data --dataset enron
```

Full loading also checks record headers, lengths, and dimensions.

## Build indexes and profile queries

For the simplest three-command build, index, and efSearch sweep workflow, see
[BENCHMARKING.md](BENCHMARKING.md).

The following runs five search configurations on SIFT1M. Both graph builds
use `M=48`, `ef_construction=80`, and seed `100`. Each pair of modes loads
the same index for its algorithm. The two algorithms build different graphs.
Run these commands from the repository root after building the driver:

```bash
python3 experiments/profiling/scripts/build_hnsw_index.py --dataset sift --M 48 --ef-construction 80 --seed 100
python3 experiments/profiling/scripts/build_shg_index.py --dataset sift --M 48 --ef-construction 80 --seed 100

# HNSW without search-time software prefetch hints
python3 experiments/profiling/scripts/profile_hnsw_query.py --dataset sift --M 48 --ef-construction 80 --k 20 --ef-search 64 --prefetch-mode off

# The same HNSW index with its original software prefetch hints
python3 experiments/profiling/scripts/profile_hnsw_query.py --dataset sift --M 48 --ef-construction 80 --k 20 --ef-search 64 --prefetch-mode native

# HEDS/SHG without the added software prefetch hints
python3 experiments/profiling/scripts/profile_shg_query.py --dataset sift --M 48 --ef-construction 80 --k 20 --ef-search 64 --prefetch-mode baseline

# HEDS/SHG with shortcut destination and base-layer lookahead prefetching
python3 experiments/profiling/scripts/profile_shg_query.py --dataset sift --M 48 --ef-construction 80 --k 20 --ef-search 64 --prefetch-mode lookahead

# Experimental bench_prune counterpart: SHG without base-layer pruning or added prefetch hints
python3 experiments/profiling/scripts/profile_shg_query.py --dataset sift --M 48 --ef-construction 80 --k 20 --ef-search 64 --prefetch-mode baseline --base-pruning off
```

Replace `sift` with `enron` or `gist` in every command for those datasets. Existing index
files are protected: add `--force` to a build command only when intentionally
rebuilding it. SHG `baseline` disables the added search prefetch hints;
`skip` enables destination prefetching alone, while `cluster` also prefetches
two candidate neighbors. Cluster mode is experimental. The defaults are
`native` for HNSW and `lookahead` for SHG. Set the mode before timing; no
rebuild is needed to switch modes.

`--base-pruning off` disables SHG's two base-layer screening checks while
keeping upper-layer pruning, shortcuts, and the usual result-heap stopping
rule. It is an adaptation of `SHG_noprune` from
`/home/suyash/opt-SHG/SHG-Index/bench_prune`, using
this profiler's saved SHG index and timing method. Its recall and search work
may differ from the pruned SHG modes. The default is `--base-pruning on`.

These are **search-time** modes. The paired HNSW runs and the paired pruned
SHG runs differ only in prefetch hints. All SHG runs reuse their saved index.
Native HNSW's build-time prefetch instructions remain unchanged in both HNSW
runs. SHG uses a different index and search procedure from HNSW.
The Python wrappers give nondefault modes distinct default result and
observation paths; for repeated runs, specify unique `--output`,
`--performance-output`, and `--layer-averages-output` paths.

### Other parameter choices

```bash
python3 experiments/profiling/scripts/build_hnsw_index.py --dataset sift --M 16 --ef-construction 200 --seed 100 --force
python3 experiments/profiling/scripts/profile_hnsw_query.py --dataset sift --M 16 --k 10 --ef-search 64
python3 experiments/profiling/scripts/build_shg_index.py --dataset sift --M 48 --ef-construction 80 --seed 100 --force
python3 experiments/profiling/scripts/profile_shg_query.py --dataset sift --M 48 --k 10 --ef-search 64
```

Use `--dataset enron` or `--dataset gist` for the other datasets. Both algorithms require `--threads 1`;
search requires `ef-search >= k`, with k no greater than the base count or
ground-truth width. Defaults are HNSW `M=16`, `ef-construction=200`; SHG
`M=48`, `ef-construction=80`; and `seed=100`, `k=10`, `ef-search=64`,
`warmup=500`.

Indexes live in `experiments/profiling/indexes/<dataset>/`. SHG needs both
its `.index` and companion `.index.shg` file. Searches load saved indexes.
Builds replace an index only with `--force`. The default filename includes M
but not construction breadth or seed; use `--index-file` to keep those graphs
separate. Scripts accept `--data-root` and `--executable` for custom paths.

For repeated measurements, output files, plots, counter definitions, and
comparison rules, see [BENCHMARKING.md](BENCHMARKING.md).
