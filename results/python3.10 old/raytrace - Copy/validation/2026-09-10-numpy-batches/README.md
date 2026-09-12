# NumPy ray batches: local implementation and validation

The optimized benchmark now renders batches of rays with NumPy, including
camera directions, ordered intersections, shadows, reflections, and shading.
`--batch-size` defaults to **1024**, the fastest of the requested sizes in the
local sweep. The scalar geometry/shading methods remain available, and the
complete pre-NumPy benchmark is preserved as `baseline.py`.

## Local performance

Windows CPython 3.12.14, NumPy 2.5.3, pyperf 2.10.0, 100x100 pixels, CPU affinity
0. These are local measurements, not assignment-server results. Scene creation,
numeric-array preparation, canvas initialization, rendering, and plotting are
inside the timer; imports and optional PPM writing remain outside it.

Initial sweep: three separate worker processes per variant, three values and
one warmup per worker, one render per value. Order was forward, reversed, then
rotated. The small number of values and substantial variability make this an
exploratory batch-size comparison:

| Variant | Mean +/- standard deviation | Scalar time / variant time |
|---|---:|---:|
| Pre-NumPy scalar | 205.3 +/- 19.8 ms | 1.00x |
| Batch 1 | 6113.6 +/- 188.5 ms | 0.034x (29.8x slower) |
| Batch 2 | 3291.6 +/- 99.8 ms | 0.062x (16.0x slower) |
| Batch 10 | 786.1 +/- 58.1 ms | 0.26x (3.83x slower) |
| Batch 100 | 169.3 +/- 9.5 ms | 1.21x |
| Batch 256 | 101.5 +/- 12.3 ms | 2.02x |
| Batch 512 | 71.6 +/- 15.7 ms | 2.87x |
| Batch 1024 | 52.0 +/- 13.1 ms | 3.94x |

Batch 1024 was fastest in each sweep round. A longer confirmation alternated
scalar/default order over four rounds, with five measured values and two warmups
per worker, four renders per value (20 normalized values per variant):

| Confirmation | Mean +/- standard deviation |
|---|---:|
| Pre-NumPy scalar | 199.0 +/- 9.1 ms |
| Default batch 1024 | 46.2 +/- 1.4 ms |

This gives **4.31x local speedup**, or about **76.8% less rendering time**.
All four confirmation rounds favoured the batched renderer. Retain pyperf's
warnings when interpreting these preliminary desktop results, and repeat on
the server. Do not combine the sweep's baseline with confirmation timings.

Small batches spend more time invoking NumPy, allocating arrays, indexing, and
managing masks than they save in arithmetic. Larger batches spread this cost
across more rays. This sweep does not establish an optimal size above 1024 or
predict the optimum at different resolutions or on different CPUs.

## Equivalence and execution checks

- All 13 existing tests passed with the new renderer, and were rerun after
  selecting the final default.
- All nine additional batch tests passed. Every requested batch size matches
  original RGB bytes and packed binary64 colours at 100x100, 200x200, and 160x120.
- Primary rays match exactly, including miss rays and partial final batches.
  Tests cover normalization, sphere roots, thresholds, ties, halfspace parallel
  rays, shadow early exit, beyond-light blockers, checker transitions, material
  coefficients, and reflection depth on the array implementation.
- CLI smoke at 12x9 with batch 10 verified worker argument forwarding and exact
  PPM output against the saved scalar baseline.
- An 800x800 render with the default batch size exactly matches the saved server
  original PPM. SHA-256:
  `3f8c8bbca2bd3188ba3ad3b95ae29950c53e1f534983d82a6af15256ab3d59f0`.
- A separate CPU-time check pinned to CPU 0 found one active rendering thread.
  NumPy created three additional Windows helper threads, but all accumulated
  zero CPU time during ten renders. See `thread_check.json`.

No runtime geometry safety checks, precision reductions, approximate arithmetic,
new intersection algorithms, or custom native extensions were added. Existing
Python canvas conversion remains in use. NumPy is the new dependency.

## SIMD evidence and limits

Local NumPy dispatch reports `X86_V3` for float64 add, subtract, multiply, and
divide; sqrt reports `baseline(X86_V2)`. Full runtime and kernel descriptions
are saved in `numpy_runtime.txt` and `numpy_dispatch.json`.

This identifies selected compiled targets, not the count of SIMD instructions
executed by the renderer. Strides, masks, and short arrays can select different
paths inside a kernel. The measured gain includes removing Python overhead;
it is not a measured SIMD-only speedup. Batch size is independent of SIMD width.
See NumPy's [dispatch introspection documentation](https://numpy.org/doc/stable/reference/generated/numpy.lib.introspect.opt_func_info.html).

## Artifacts and server reproduction

- `baseline.py`: snapshot before NumPy.
- `optimized_measured.py`: source used in the initial sweep; final production
  differs only by changing the default from 256 to 1024. Sweep commands passed
  batch sizes explicitly, so that default did not affect their results.
- `measurement_metadata.json`: source hashes, interpreter, and sweep order.
- `measure_local.py`: sweep driver; pass a fresh output directory to rerun.
- `round-*.json`, `scalar.json`, `batch-*.json`, `timing_summary.json`, and
  `benchmark_log.txt`: raw and aggregated sweep results and commands.
- `confirm-*.json`, `confirmed-*.json`, `confirmation_summary.json`,
  `confirmation_comparison.txt`, `confirmation_log.txt`: final default comparison.
- `cli.json`, `cli.ppm`, `baseline-cli.ppm`, `default-800.json`, and
  `batched-800.ppm`: CLI/default verification artifacts. The 800x800 JSON is one
  diagnostic value and is not used as a repeatable timing estimate.
- `validation_summary.json`: final hashes and verification summary.

Install NumPy in both server environments, run tests there, then compare against
this round's saved scalar baseline. The full commands and batch-size sweep are
in the fourth-pass section of
[OPTIMIZATIONS.md](../../../../../suites/optimized/bm_raytrace/OPTIMIZATIONS.md).

Example full pipeline after dependency installation:

```bash
./scripts/run_one.sh raytrace optimized --fast --width 800 --height 800 --batch-size 1024
```

This forwards the selected size to timing, counting, debug-Python profiling,
and image generation. The shell script was syntax-checked locally; Linux perf
execution and the server's NumPy build still require server validation.
