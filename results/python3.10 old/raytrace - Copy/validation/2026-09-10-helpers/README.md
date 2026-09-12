# Four arithmetic helpers: local validation, 2026-09-10

Implemented `Vector.normalized`, `Vector.reflectThrough`, `Ray.pointAtTime`, and
`Sphere.normalAt` with direct scalar arithmetic and fewer temporary vectors.
The reference for this round is the already-optimized renderer in `baseline.py`,
not the untouched original or the historical 323 ms server measurement.

## Correctness

All 12 tests in `tests/test_raytrace.py` passed for the baseline, each of the four
independent variants, and the combined implementation. They compare against the
untouched original: RGB bytes and pre-conversion binary64 colours match exactly
at 100x100, 200x200, and 160x120. Direct helper comparisons cover coordinate bits,
return types, unchanged inputs, signed zero, subnormal squared lengths, and
small/large finite coordinates. Existing geometry, shadow, checker, recursion,
and pixel tests also pass.

An AST audit confirmed that only the four approved production methods changed.
The final source hash matches the measured combined snapshot. Existing comments
are preserved apart from the directly affected hit-point explanation.

## Timings

Environment: Windows CPython 3.12.14, pyperf 2.10.0, one thread pinned to logical
CPU 0, 100x100 input. These are preliminary local results, not measurements from
the Linux/Python 3.10 assignment VM.

Each independent variant changes only the named helper relative to `baseline.py`.
The combined variant changes all four. Two passes used eight processes, five
values per process, one warmup, and one loop: 40 measured values per variant per
pass. The repeat reversed the variant order. Times are milliseconds, mean +/-
standard deviation.

| Variant | Initial | Reverse-order repeat | Interpretation |
| --- | ---: | ---: | --- |
| Current optimized baseline | 220.23 +/- 11.16 | 222.10 +/- 8.33 | Fresh reference for this round. |
| Normalization only | 214.70 +/- 10.14 | 219.64 +/- 13.85 | Initial difference significant in pyperf; repeat inconclusive. |
| Reflection only | 217.49 +/- 9.83 | 218.81 +/- 8.89 | Inconclusive in both passes. |
| Hit-point calculation only | 219.50 +/- 9.49 | 221.11 +/- 12.79 | Inconclusive in both passes. |
| Sphere normal only | 221.34 +/- 12.42 | 220.26 +/- 9.18 | Inconclusive in both passes. |
| All four | 223.81 +/- 18.78 | 209.84 +/- 12.46 | Initial difference inconclusive; repeat 1.06x faster. |

Pyperf warned about instability. None of the individual changes demonstrated a
statistically significant improvement in both passes. The combined results
disagreed, so six additional adjacent baseline/combined pairs were collected,
alternating which implementation ran first. Each invocation used one process,
eight measured values, two warmups, one loop, and the same CPU affinity.

| Pair | Baseline mean | Combined mean | Baseline / combined |
| --- | ---: | ---: | ---: |
| 1 | 215.18 | 216.13 | 1.00x |
| 2 | 229.20 | 208.33 | 1.10x |
| 3 | 228.64 | 211.97 | 1.08x |
| 4 | 212.71 | 212.21 | 1.00x |
| 5 | 227.12 | 197.68 | 1.15x |
| 6 | 214.63 | 205.28 | 1.05x |

The paired means average 221.24 ms baseline and 208.60 ms combined (about 1.06x
faster, or 5.7% less time); combined was faster in five of six pairs. This
suggests a modest combined benefit, but is not a guaranteed or server-validated
speedup. Keep the inconclusive initial pass when reporting the results.

## Separate work counts

Instrumentation of one 100x100 render was performed separately, never inside
timed runs. It confirms less object/method overhead while retaining the same
geometric intersection workload.

| Operation | Baseline | Combined |
| --- | ---: | ---: |
| Vector construction | 85,013 | 67,538 |
| Point construction | 5,345 | 5,345 |
| Ray construction | 26,000 | 26,000 |
| `Vector.magnitude` calls | 27,479 | 0 |
| `Vector.dot` calls | 68,549 | 41,070 |
| `Vector.scale` calls | 43,678 | 200 |
| Sphere intersection tests | 179,457 | 179,457 |
| Halfspace intersection tests | 25,501 | 25,501 |

Vector constructions fell about 20.6%. The removed helper calls were replaced
by their arithmetic; zero `magnitude` calls does not mean zero square roots.
These are software call counts, not hardware memory traffic or energy counters.

## Artifacts and server validation

- `baseline.py` and `baseline_metadata.json`: exact pre-round source and hashes.
- `variants.json` and `variants.patch`: source hashes and independent/combined
  changes relative to the baseline, including LF-normalized hashes for Git copies.
- `*-initial.json`, `*-repeat.json`, and `pair-*.json`: all raw pyperf measurements.
- `summary.json` and `comparisons.txt`: statistics, commands, checks, and pyperf
  significance reports.

Matched-run server commands are in
`suites/optimized/bm_raytrace/OPTIMIZATIONS.md`. They compare this saved baseline
with the current optimized source in a fresh output directory. No existing
result history was overwritten. No NumPy, SIMD, native code, threads, new runtime
dependencies, or safety checks were introduced, and no Linux perf counters were
collected locally.
