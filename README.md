# Shortcut-enabled Hierarchical Graph (SHG) index

## Introduction

This repository implements the SHG index on top of [hnswlib](https://github.com/nmslib/hnswlib). `pgm` is the learned index used for shortcuts; `hnswlib/heds.h` implements SHG.

## Compilation 

```bash
mkdir build
cd build
cmake ..
make
```

## Usage 
`./example_search {algName} {dataset} {k}`

```bash
./example_search heds enron 20
```
This runs a 20-nearest-neighbor search on Enron. Unzip the dataset into `enron/` first.

## Dataset
Input data such as `enron.data_new` use this binary layout:
```
{Bytes of the data type (int)} {The size of the vectors (int)} {The dimension of the vectors (int)} {All of the binary vector, arranged in turn (float)}
```
Convert other datasets to this format, name the file `[datasetName].data_new`, and update the data path.

## Native HNSW/SHG profiling

For reproducible SIFT1M and Enron build/search measurements, query-local
per-layer hops and distance statistics, recall and CSV reports, see
[experiments/profiling/README.md](experiments/profiling/README.md).

## SHG software prefetching

SHG search defaults to shortcut destination prefetching and two-neighbor
lookahead in the base layer. The hints do not change graph traversal or
distance calculations. Select a mode on an `HEDS` instance before searching:

```cpp
index.setPrefetchMode(hnswlib::PrefetchMode::Baseline);          // no hints
index.setPrefetchMode(hnswlib::PrefetchMode::Skip);              // destination only
index.setPrefetchMode(hnswlib::PrefetchMode::SkipAndLookahead);  // default
index.setPrefetchMode(hnswlib::PrefetchMode::Cluster);           // also prefetch two neighbors
```

Cluster mode builds a small per-node lookup table and is optional because its
extra memory traffic can make searches slower. Mode changes should happen
between searches, not concurrently with them.
