# Recreate the efSearch sweep

From the repository root, with SIFT, Enron, and GIST data in
`experiments/profiling/data/`, run these three commands:

```bash
bash experiments/profiling/scripts/build_profiler.sh --optimization O3
bash experiments/profiling/scripts/build_sweep_indexes.sh
bash experiments/profiling/scripts/run_ef_search_sweep.sh
```

Step 1 accepts `--optimization Ofast` instead. Step 2 builds HNSW and SHG
indexes with `M=48`, `ef-construction=80`, and seed 100. It reports saved
indexes and skips them; use `--force` to rebuild. Step 3 searches both
algorithms at efSearch values 20, 24, 32, 48, 64, 96, 128, 192, 256, and 512,
with five repeats per point. It includes the HNSW prefetch modes and the SHG
prefetch/pruning modes. Changing the optimization flag for search only does
not require rebuilding indexes.

For a smaller run, pass `--datasets "sift"` to both the index and search
scripts, and optionally `--ef-values "20 64 128" --repeats 1` to the search
script. Run each script with `--help` for other options. Sweep results go under
`experiments/profiling/results/ef_search_sweep/run_N/` and performance
observations under `experiments/profiling/observations/ef_search_sweep/run_N/`.
The sweep picks the next number found in either location, starting with
`run_1`. Pass `--run-id run_N` only to choose a specific unused number.
