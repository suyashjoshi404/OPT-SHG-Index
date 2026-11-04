#pragma once

#include <algorithm>
#include <cstddef>
#include <cstdint>

#if defined(__SSE__) || defined(_M_IX86) || defined(_M_X64)
#include <xmmintrin.h>
#endif

namespace hnswlib {

// Modes are per index, so separate indexes can be benchmarked independently.
enum class PrefetchMode { Baseline, Skip, SkipAndLookahead, Cluster, IDEA2_V2 = 5 };

class PrefetchController {
 public:
    static inline bool skip_enabled(PrefetchMode mode) {
        return mode != PrefetchMode::Baseline;
    }

    static inline bool lookahead_enabled(PrefetchMode mode) {
        return mode == PrefetchMode::SkipAndLookahead || mode == PrefetchMode::Cluster;
    }

    // Idea 2.0 is selected per index, like the existing prefetch modes.
    static inline bool enable_v2(PrefetchMode mode) {
        return mode == PrefetchMode::IDEA2_V2;
    }

    static constexpr size_t v2_dist = 2;
    static constexpr size_t v2_lines = 3;

    static inline void prefetch_lines(const void* address, size_t bytes, size_t max_lines) {
        if (!address) return;
        const char* p = static_cast<const char*>(address);
        const size_t lines = std::min((bytes + 63) / 64, max_lines);
        for (size_t i = 0; i < lines; ++i) {
#if defined(__SSE__) || defined(_M_IX86) || defined(_M_X64)
            _mm_prefetch(p + i * 64, _MM_HINT_T0);
#elif defined(__GNUC__) || defined(__clang__)
            __builtin_prefetch(p + i * 64, 0, 3);
#endif
        }
    }

    template <typename LinkFn, typename VectorFn>
    static inline void on_layer_transition(PrefetchMode mode, unsigned int node,
                                           int destination, LinkFn link, VectorFn vector,
                                           size_t vector_bytes, size_t link_bytes,
                                           size_t node_count) {
        if (!skip_enabled(mode) || destination < 0 || node >= node_count) return;
        const void* links = link(node, destination);
        prefetch_lines(links, link_bytes, 2);
        prefetch_lines(vector(node), vector_bytes, 4);
        if (links) {
            const uint32_t* list = static_cast<const uint32_t*>(links);
            // The graph stores its count in the low 16 bits of the first word.
            if ((list[0] & 0xffffU) && list[1] < node_count)
                prefetch_lines(vector(list[1]), vector_bytes, 2);
        }
    }

    template <typename VisitedType, typename VectorFn>
    static inline void on_neighbor_lookahead(PrefetchMode mode, const int* links,
                                             size_t current, size_t count,
                                             const VisitedType* visited, VectorFn vector,
                                             size_t vector_bytes, size_t node_count) {
        if (!lookahead_enabled(mode) || current + 2 > count) return;
        const int ahead = links[current + 2];
        if (ahead < 0 || static_cast<size_t>(ahead) >= node_count) return;
        prefetch_lines(&visited[ahead], sizeof(VisitedType), 1);
        prefetch_lines(vector(static_cast<unsigned int>(ahead)), vector_bytes, 3);
    }

    template <typename LinkFn>
    static inline void on_next_candidate(PrefetchMode mode, unsigned int node,
                                         LinkFn link, size_t link_bytes, size_t node_count) {
        if ((lookahead_enabled(mode) || enable_v2(mode)) && node < node_count)
            prefetch_lines(link(node), link_bytes, 2);
    }

    template <typename VisitedType, typename VectorFn>
    static inline void v2_prologue(PrefetchMode mode, const int* links, size_t count,
                                   const VisitedType* visited, VectorFn vector,
                                   size_t vector_bytes, size_t node_count) {
        if (!enable_v2(mode)) return;
        const size_t flags_to = std::min(2 * v2_dist, count);
        const size_t vectors_to = std::min(v2_dist, count);
        for (size_t k = 1; k <= flags_to; ++k) {
            const int id = links[k];
            if (id >= 0 && static_cast<size_t>(id) < node_count)
                prefetch_lines(&visited[id], sizeof(VisitedType), 1);
        }
        for (size_t k = 1; k <= vectors_to; ++k) {
            const int id = links[k];
            if (id >= 0 && static_cast<size_t>(id) < node_count)
                prefetch_lines(vector(static_cast<unsigned int>(id)), vector_bytes, v2_lines);
        }
    }

    template <typename VisitedType, typename VectorFn>
    static inline void v2_step(PrefetchMode mode, const int* links, size_t current,
                               size_t count, const VisitedType* visited,
                               VisitedType tag, VectorFn vector,
                               size_t vector_bytes, size_t node_count) {
        if (!enable_v2(mode)) return;
        const size_t flag_pos = current + 2 * v2_dist;
        const size_t vector_pos = current + v2_dist;
        if (flag_pos <= count) {
            const int id = links[flag_pos];
            if (id >= 0 && static_cast<size_t>(id) < node_count)
                prefetch_lines(&visited[id], sizeof(VisitedType), 1);
        }
        if (vector_pos <= count) {
            const int id = links[vector_pos];
            if (id >= 0 && static_cast<size_t>(id) < node_count && visited[id] != tag)
                prefetch_lines(vector(static_cast<unsigned int>(id)), vector_bytes, v2_lines);
        }
    }
};

}  // namespace hnswlib
