# Local raytrace validation, 2026-09-09

All seven primary Python optimizations are implemented. At 100x100, the complete
combination measured **2.12x faster** in the initial pass and **2.11x faster** in
the reverse-order repeat. This is local evidence from **Windows CPython 3.12.14,
pyperf 2.10.0, one thread pinned to logical CPU 0**, not an assignment-VM result.

## Cumulative stage timings

Each row adds one change to the preceding row. Times are mean +/- standard
deviation in milliseconds. Initial runs used `--fast` (20 measured values per
stage); repeats used six processes, eight values, two warmups, and one loop
(48 measured values per stage). The second pass reversed stage order.

| Stage | Initial | Repeat |
| --- | ---: | ---: |
| Pre-change renderer | 465.3 +/- 10.3 | 460.2 +/- 10.2 |
| Reuse shadow rays | 359.6 +/- 13.9 | 356.0 +/- 15.0 |
| Cache camera components | 352.9 +/- 10.5 | 352.9 +/- 35.0 |
| Select closest hit during traversal | 341.4 +/- 9.0 | 343.0 +/- 27.7 |
| Scalar sphere calculations | 232.8 +/- 7.8 | 227.8 +/- 8.6 |
| Slots for temporary geometry objects | 228.5 +/- 9.2 | 231.9 +/- 11.8 |
| Reuse directions for diffuse lighting | 215.3 +/- 6.6 | 220.9 +/- 17.4 |
| Remove discarded checker scaling | 219.3 +/- 12.6 | 218.6 +/- 16.0 |

Pyperf warned about instability. The complete improvement repeated, but the
isolated camera-cache, slots, and checker-cleanup gains are inconclusive. These
remain implemented candidates awaiting the plan's final acceptance measurements
on the assignment VM; do not claim individually proven speedups for them. The
stages are cumulative experiments, not independent additive speedup estimates.

The initial and repeated raw pyperf JSON files are retained here. `summary.json`
records commands, source hashes, exact statistics, checks, and limitations.
`stages.diff` records the successive source changes, starting with the untouched
original to pre-change optimized comment differences. Existing historical result
directories were not changed.

## Correctness and work counts

`tests/test_raytrace.py` passed all eight tests. Full renders match both RGB
bytes and packed binary64 colours before pixel conversion at 100x100, 200x200,
and 160x120. Every intermediate stage also matches at 100x100. The pre-change
optimized source and untouched original have identical Python ASTs.

Separate instrumentation of one 100x100 render counted the following calls.
Instrumentation was absent from timed runs.

| Operation | Pre-change | Complete combination |
| --- | ---: | ---: |
| Vector construction | 452,943 | 85,013 |
| Point construction | 5,345 | 5,345 |
| Ray construction | 98,172 | 26,000 |
| Vector normalization | 109,887 | 27,479 |
| Sphere intersection | 179,457 | 179,457 |
| Halfspace intersection | 25,501 | 25,501 |

The number of geometric intersection tests stayed identical while vector
construction fell about 81% and normalization about 75%. These are software
call counts, not measured hardware instructions, cache events, or energy use.

See `suites/optimized/bm_raytrace/OPTIMIZATIONS.md` for correctness commands,
fresh matched-input VM timings, fixed-work perf collection, and deferred native
and SIMD work. No Linux perf counters or native/SIMD results were collected here.
