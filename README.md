# Improving Performance of Hierarchical Graphs

Run all commands from the repository root. The Enron archive (`enron.zip`) is
in the repository root. Supply `sift.zip` and `gist.zip` locally if you want to
run SIFT or GIST; they are excluded from Git. Extracted datasets are also
excluded from Git. You need a C++17 compiler, CMake 3.16+, Python 3.8+, and
Matplotlib for plotting.

## Set up the datasets

Create a directory for each dataset you have and unzip its archive into that
directory. For example, to set up all three:

```bash
mkdir -p experiments/profiling/data/{sift,enron,gist}
unzip sift.zip -d experiments/profiling/data/sift
unzip enron.zip -d experiments/profiling/data/enron
unzip gist.zip -d experiments/profiling/data/gist
```

The archives contain files directly at their root, so each dataset's files
end up in `experiments/profiling/data/<dataset>/`. If the files are already
present there, you can skip the corresponding unzip command.

## Run the experiments

1. Build the native HNSW/SHG profiler:

   ```bash
   bash experiments/profiling/scripts/build_profiler.sh
   ```

2. Build the HNSW and SHG indexes. Existing complete indexes are reused:

   ```bash
   bash experiments/profiling/scripts/build_sweep_indexes.sh
   ```

3. Search the saved indexes across efSearch values:

   ```bash
   bash experiments/profiling/scripts/run_ef_search_sweep.sh
   ```

   The default sweep covers all three datasets, ten efSearch values, and five
   repeats. Each benchmark run is named `run_N`.

4. Plot recall versus latency and QPS. Replace `run_1` with the run number
   printed in step 3:

   ```bash
   python3 experiments/profiling/scripts/plot_ef_search_sweep.py \
     experiments/profiling/observations/ef_search_sweep/run_1
   ```

   The recall–latency plot needs different efSearch values to show a curve.

Indexes are saved under `experiments/profiling/indexes/`. Query results go to
`experiments/profiling/results/ef_search_sweep/run_N/`; performance CSVs and
plots go to `experiments/profiling/observations/ef_search_sweep/run_N/`.
Use `--help` on either sweep script for options. For a short SIFT run, pass
`--datasets "sift"` to both scripts and `--ef-values "20 64 128" --repeats 1`
to the search script. Add `--force` to the index script to rebuild indexes.

## Simple Enron example

1. Build the profiler if you have not already:

   ```bash
   bash experiments/profiling/scripts/build_profiler.sh
   ```

2. Build one HNSW and one SHG index on Enron, then search both with `k=20`
   and `efSearch=64`:

   ```bash
   bash experiments/profiling/scripts/example_enron.sh
   ```

3. Inspect the performance CSVs:

   ```bash
   head -n 3 experiments/profiling/observations/enron_example/hnsw_search.csv
   head -n 3 experiments/profiling/observations/enron_example/shg_search.csv
   ```

The indexes are in `experiments/profiling/indexes/enron/`. Per-query results
are in `experiments/profiling/results/enron_example/`.
