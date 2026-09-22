# 0460882-Project-HwiSwiCoDesign
Directory links incase confused:

1. Original Raytrace code folder: https://github.com/Tydox/0460882-Project-HwiSwiCoDesign/tree/main/suites/original/bm_raytrace

2. Optimized Raytrace code folder: https://github.com/Tydox/0460882-Project-HwiSwiCoDesign/tree/main/suites/original/bm_raytrace
3. Original Plyflate: https://github.com/Tydox/0460882-Project-HwiSwiCoDesign/tree/main/suites/original/bm_pyflate
4. Optimized Pyflate: https://github.com/Tydox/0460882-Project-HwiSwiCoDesign/tree/main/suites/optimized/bm_pyflate

5. Results RayTrace folder: https://github.com/Tydox/0460882-Project-HwiSwiCoDesign/tree/main/results/raytrace

6. Results Pyflate Folder: https://github.com/Tydox/0460882-Project-HwiSwiCoDesign/tree/main/results/pyflate

## 0. Pull this git
Copy this entire folder to the QEMU server, the scripts are in the scripts folder.


## 1. One-time setup in the Ubuntu QEMU VM
After you are in the folder:
```bash
cd 0460882-Project-HwiSwiCoDesign
```
Then run this to make the scripts runable

```bash
chmod +x scripts/*.sh
./scripts/setup_ubuntu.sh
```

this will install:

- `python3.12`, `python3.12-dbg`, `git`, `perl`, `perf`,`pyperformance`, `pyperf`, Brendan Gregg's official FlameGraph scripts.

It creates two Python 3.12 environments without replacing Ubuntu's system
`python3` command:

- `.venv312`: normal Python 3.12, used for **timing** comparisons. to not use the dbg overhead for timing.
- `.venv312-dbg`: debug Python 3.12, used for profiling. Its perf trampoline
  exposes names such as `py::BatchedRenderer.render`.


# Ohad from here you only need to run:
**We give you the full code as a template to make it easier for you :)**

**just choose how many iterations you want and the code block is all you need**
## Pyflate:

1. Full 20 iterations
```bash
./scripts/run_one.sh pyflate original 
./scripts/run_one.sh pyflate optimized 
./scripts/compare.sh pyflate #this just compared time not mandatory
```
2. Half 10 iterations
```bash
./scripts/run_one.sh pyflate original --fast
./scripts/run_one.sh pyflate optimized --fast #10 iteration
./scripts/compare.sh pyflate 
```
3. Single iteration
```bash
./scripts/run_one.sh pyflate original --debug-single-value
./scripts/run_one.sh pyflate optimized --debug-single-value #one iteration
./scripts/compare.sh pyflate 
```



## RayTracing:

### Steps:
you can change the image size, we used 800x800, if want shorter than make specify it, we changed it from 100x100.

### 1. Go into the folder

```bash
cd 0460882-Project-HwiSwiCoDesign
```
We tested full vs fast vs single run, the server would slowdown too much with full and fast due to the file the perf was generating with all the data, so we did a run with single at the size of 800x800. we did once run on full, and got the same values for mean+-std, so we saw it's not needed as the std =0.2 a single run was suffice.


### 2. Run the Raytracing benchmark - choose how many runs you want to average.

1. Option 1 - 20 iterations
```bash
./scripts/run_one.sh raytrace original --width 800 --height 800
./scripts/run_one.sh raytrace optimized --width 800 --height 800 --batch-size 2048
./scripts/compare.sh raytrace
```
2. Option 2 - 10 iterations
```bash
./scripts/run_one.sh raytrace original --fast --width 800 --height 800
./scripts/run_one.sh raytrace optimized --fast --width 800 --height 800 --batch-size 2048
./scripts/compare.sh raytrace
```
3. **Option 3 - 1 iteration - We recommend to do this for 800x800 image on the server**
```bash
./scripts/run_one.sh raytrace original --debug-single-value --width 800 --height 800
./scripts/run_one.sh raytrace optimized --debug-single-value --width 800 --height 800 --batch-size 2048
./scripts/compare.sh raytrace
```


`--fast` uses pyperformance's short timing mode for pipeline testing.
`--debug-single-value` computes one value for the shortest diagnostic run. The
selected mode applies to timing, counter collection, and profiling; do not pass
both mode flags.

# 
Now it's not comfy to view the files so we push them back to our repo, and then pull to our local pc, and then we can view all the files, below is the structure:

---
## Outputs

The original baseline has one stable directory. Each optimized run gets its own
minute-stamped history directory:

```text
results/<benchmark>/original/
results/<benchmark>/optimized/YYYY-MM-DD-HH-MM/
```

For example:

```text
results/raytrace/
├── original/
│   ├── timing.json
│   ├── perf_report.txt
│   ├── flamegraph.svg
│   └── run_metadata.txt
└── optimized/
    ├── 2026-09-02-15-30/
    │   ├── timing.json
    │   ├── perf.data
    │   ├── perf_report.txt
    │   ├── perf_script.txt
    │   ├── speedscope.folded
    │   ├── flamegraph.svg
    │   ├── run_metadata.txt
    │   └── comparison.txt
    ├── 2026-09-02-16-10/
    │   └── ...
    └── latest -> 2026-09-02-16-10
```

Files are saved in the same original or timestamped optimized folder:

| File | Contents |
| --- | --- |
| `perf_stat.txt` | Counter totals and perf's derived metrics from normal Python; separate from sampled profiles. |
| `perf_events.txt` | Tab-separated status of every candidate for stat and recording. |
| `perf_probe.log` | Individual event support probes and their errors, including unsupported VM counters. |
| `perf_record.log` | Recording diagnostics, including any sampling warnings. |
| `speedscope.folded` | Compact complete call stacks for Speedscope and flame-graph generation. |
| `flramgehraph.svg` | the image. |

The candidate list covers all unique events from `perf list hw` and
`perf list sw` supplied for this project, plus frontend/backend stalled cycles,
L1/LLC cache accesses and misses, prefetches, instruction/data TLB events,
branch-cache events, NUMA node accesses, and `user_time`/`system_time`.
Each candidate is tested locally: availability depends on the kernel, perf
version, CPU, and VM's exposed counters. Aliases are requested only once.
`duration_time`, `user_time`, and `system_time` are stat-only. `dummy` and
`bpf-output` are probed for stat support but excluded from benchmark collection:
dummy generates no samples, and BPF output needs a separate BPF producer.
CPU-specific raw events, tracepoints, and system-wide uncore events are outside
this generic process-counter list.

`perf_events.txt` and `perf_probe.log` retain the availability results for all
candidate sampling events. The main `perf record` pass deliberately records
only `cpu-clock` at 199 Hz: this avoids multiplexing unrelated sampling events
and gives `perf_report.txt` and `flamegraph.svg` one clear meaning--sampled CPU
time. The recording uses Python 3.12 debug as required for native CPython
symbols. `PYTHONPERFSUPPORT=1` enables Python's perf trampolines in the initial
process and inherited pyperf workers, producing `py::function:file` symbols.
Frame-pointer callchains keep `perf.data` compact and make report/flamegraph
processing much faster than DWARF stack snapshots. Perf runs with privileges
so kernel mappings and symbols can be included when the guest kernel exposes
them. `--no-bpf-event` requests that perf skip unrelated synthesis of
pre-existing BPF images.

`perf_report.txt` includes the perf-data header, sample counts, total periods,
demangled symbols, `Children` and `Self` percentages, and caller trees. Top-level
rows below 0.1% are hidden, and call-tree branches below 0.5% are hidden to keep
the text readable. The icicle graph visualizes the wider paths, while all paths
remain available in `speedscope.folded`. Folded weights are actual sample counts
rather than raw `cpu-clock` periods. The metadata distinguishes the single
recorded profile event from all events that passed the availability probe.


___

# Ohad you dont need to do this as if you copied our entire git folder it will have them, but to add benchmarks you write this command and then edit the code in the "\suites\optimized\" subfolder

```bash
./scripts/add_benchmark.sh raytrace
./scripts/add_benchmark.sh pyflate
```


This keeps each benchmark in two independent suites:

```text
suites/original/bm_<name>/run_benchmark.py   # never edit
suites/optimized/bm_<name>/run_benchmark.py  # edit this file
```


