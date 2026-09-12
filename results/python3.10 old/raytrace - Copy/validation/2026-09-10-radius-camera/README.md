# Radius caching and camera-ray temporaries

Both approved changes are implemented in the optimized renderer. This round's
baseline already includes the four scalar arithmetic helper optimizations.
The original renderer and historical results are unchanged.

## Preliminary local timings

Windows CPython 3.12.14, pyperf 2.10.0, 100x100 pixels, affinity to logical CPU 0.
Eight rounds rotate and reverse the four variants' execution order. Each variant
has eight worker processes with eight measured values each (64 values total).
Scene construction and rendering remain timed.

| Variant | Mean +/- standard deviation | Speedup vs this round's baseline | Faster rounds |
|---|---:|---:|---:|
| Baseline | 213.1 +/- 21.8 ms | 1.00x | -- |
| Radius cache only | 202.5 +/- 14.9 ms | 1.05x | 7/8 |
| Camera cache only | 205.0 +/- 10.0 ms | 1.04x | 8/8 |
| Both changes | 202.2 +/- 18.0 ms | 1.05x | 7/8 |

Both changes show a local benefit, but these runs contain substantial variability.
In particular, the baseline's seventh round was slower; it remains included.
The combined result does not establish an additional gain over radius caching
alone. Do not add the individual speedups together. Confirm on the server with
a fresh matching baseline before treating these as server performance claims.
Pyperf warnings and complete commands are retained in `benchmark_log.txt`.

## What changed and why

- `Sphere.__init__` computes `radiusSquared` once; `intersectionTime` reads it.
  This replaces a repeated Python multiplication with an attribute read. The
  benchmark never changes sphere radii after construction. Cache construction
  remains inside timing; no mutation handling or runtime checks were added.
- `Scene.render` caches `eye.vector + horizontalOffset` for each column.
  Pixels add the row's vertical offset to that cached vector, preserving the
  existing left-associated arithmetic and ray normalization. At 100x100 this
  avoids 9,900 temporary vectors and 29,700 coordinate additions.

Separate instrumentation of one 100x100 render confirms the work reduction:

| Operation | Baseline | Both changes |
|---|---:|---:|
| Radius-squared multiplications | 179,457 | 7 |
| Vector constructions | 67,538 | 57,638 |
| Vector additions | 20,000 | 10,100 |
| Ray constructions | 26,000 | 26,000 |
| Sphere intersection tests | 179,457 | 179,457 |
| Halfspace intersection tests | 25,501 | 25,501 |

Instrumentation was not active during timings. These changes reduce Python
bookkeeping, allocations, and arithmetic; they do not introduce SIMD.

## Validation and artifacts

All 13 tests passed for the baseline, each independent change, and the combined
renderer against the untouched original. Checks include exact image bytes and
binary64 colours at 100x100, 200x200, and 160x120; exact primary camera rays at
2x2, 100x100, and 160x120; and existing geometry/helper boundary cases.

- `baseline.py` and `baseline_metadata.json`: pre-change source and hashes.
- `variants.patch` and `variants.json`: independent changes and source hashes.
- `round-*.json`, `run_order.json`, `benchmark_log.txt`: raw timings and commands.
- `00-baseline.json` through `03-combined.json`: aggregated pyperf results.
- `comparisons.txt` and `summary.json`: comparisons, counts, and full metadata.

Matched server commands are in the third-pass section of
[OPTIMIZATIONS.md](../../../../../suites/optimized/bm_raytrace/OPTIMIZATIONS.md).
Use the saved baseline to isolate this round's gain; use the original renderer
for a cumulative comparison.

NumPy batching awaits server results and the user's explicit instruction to
continue. Requested future batch sizes are 1, 2, 10, 100, 256, 512, and 1024.
NumPy can use SIMD for supported array kernels, but using NumPy does not
guarantee SIMD execution. No batching parameter or dependency was added.
