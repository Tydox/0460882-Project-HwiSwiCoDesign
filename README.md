# 0460882-Project-HwiSwiCoDesign
Submited Project Repo, including git history for bonus points

![Alt](https://repobeats.axiom.co/api/embed/ad92f46e5b664778f6caa8c1b19150d3c0835058.svg "Repobeats analytics image")

# pyperformance optimization project starter

This starter keeps each benchmark in two independent suites:

```text
suites/original/bm_<name>/run_benchmark.py   # never edit
suites/optimized/bm_<name>/run_benchmark.py  # edit this file
```

Both suites expose the same benchmark name. This is important: `pyperf` can
compare the two JSON files only when the benchmark names match.

## 1. One-time setup in the Ubuntu QEMU VM

```bash
chmod +x scripts/*.sh
./scripts/setup_ubuntu.sh
```

The setup installs:

- Ubuntu tools: `python3`, `python3-dbg`, virtual-environment and development
  packages, `git`, `perl`, and Linux `perf` tools.
- Python tools: the current official `pyperformance` source and its declared
  dependencies. `pyperf` is installed automatically.
- Brendan Gregg's official FlameGraph scripts.

It creates two Python environments:

- `.venv`: normal Python, used for trustworthy timing comparisons.
- `.venv-dbg`: `python3-dbg`, used for readable CPython symbols in `perf`.

Do all measured runs inside the same VM with the same CPU allocation. Do not
compare a normal-Python result with a debug-Python result.

## 2. Add the selected benchmarks

For example:

```bash
./scripts/add_benchmark.sh raytrace
./scripts/add_benchmark.sh deepcopy
```

If a benchmark folder contains variants, adding the base benchmark exposes all
of them. For example, `./scripts/add_benchmark.sh pickle` also makes
`pickle_dict` available; you can then pass `pickle_dict` to the run scripts.

The name must match an upstream folder named `bm_<name>`. To see available
names:

```bash
.venv/bin/python -m pyperformance list -b all
```

`add_benchmark.sh` copies the official code into both `original` and
`optimized`. It also rebuilds both suite manifests.

## 3. Confirm the untouched pipeline quickly

```bash
./scripts/run_one.sh raytrace original --fast
./scripts/run_one.sh raytrace optimized --fast
./scripts/compare.sh raytrace
```

At this stage, the two implementations are identical, so no meaningful speedup
is expected. The purpose is only to prove that timing, `perf`, and flame-graph
generation all work before editing code.

## 4. Modify only your optimized code

For raytrace, edit:

```text
suites/optimized/bm_raytrace/run_benchmark.py
```

Normally, change the algorithm or implementation functions but preserve:

- the same inputs and workload size;
- the same result or correctness behavior;
- the `pyperf.Runner` registration at the bottom;
- the benchmark name;
- the original version in `suites/original`.

You do **not** need to edit the repository's top-level `pyproject.toml`.
Each copied benchmark has its own `pyproject.toml`; it describes the benchmark
and its dependencies. Change it only if your optimized code genuinely adds a
new Python dependency.

## 5. Run the final measurements

Run the baseline before changing the optimized source, then run the optimized
version:

```bash
./scripts/run_one.sh raytrace original
./scripts/run_one.sh raytrace optimized
./scripts/compare.sh raytrace
```

Repeat the same three commands for the second benchmark.

Choose the execution mode on each invocation:

```bash
# Regular (default)
./scripts/run_one.sh raytrace optimized

# Fast
./scripts/run_one.sh raytrace optimized --fast

# One diagnostic value
./scripts/run_one.sh raytrace optimized --debug-single-value
```

`--fast` uses pyperformance's short timing mode for pipeline testing.
`--debug-single-value` computes one value for the shortest diagnostic run. The
selected mode applies to timing and profiling; do not pass both mode flags.

Raytrace defaults to a 100x100 workload and image. Override either dimension
without editing the benchmark source:

```bash
./scripts/run_one.sh raytrace optimized --fast --width 200 --height 150
```

`--width` and `--height` accept positive integers only and are rejected for
benchmarks other than raytrace. Use the same dimensions for original and
optimized runs so their timing results remain comparable.

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
    │   ├── stacks.folded
    │   ├── flamegraph.svg
    │   ├── run_metadata.txt
    │   └── comparison.txt
    ├── 2026-09-02-16-10/
    │   └── ...
    └── latest -> 2026-09-02-16-10
```

The timestamp uses the VM's local time. The script refuses to start a second
optimized run during the same minute, ensuring that no optimized history is
overwritten. `optimized/latest` always points to the newest completed run, and
`compare.sh` automatically compares the stable original baseline with that run.

`run_metadata.txt` records the completion time, source-file hash, Git commit,
and whether the Git working tree was clean. This identifies exactly which code
produced each result.

Open `flamegraph.svg` in a browser. Wider boxes consume more sampled CPU time.
Use `perf_report.txt` for the numeric hotspot list and `timing.json` for the
statistical before/after comparison.

## Copy the complete results folder with SCP

After running both benchmarks, copy the whole `results/` tree from the VM to
the configured destination:

```bash
./scripts/upload_results.sh
```

The configured destination is:

```text
ece882-011@10.0.2.2:~/
```

This produces `~/results` on the remote machine. The first connection may ask
you to confirm the SSH host key, and every connection may request your password
unless SSH keys are configured.

To use another destination without editing the script:

```bash
REMOTE_DESTINATION='user@host:/some/path/' ./scripts/upload_results.sh
```

## GitHub version history

Create a new **empty** GitHub repository: do not initialize it with a README,
license, or `.gitignore`. Then, from this project directory:

```bash
git init
git branch -M main
git config user.name "Your Name"
git config user.email "your-github-email@example.com"

git add .
git commit -m "Set up pyperformance profiling pipeline"

git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
```

GitHub does not accept an account password for Git over HTTPS. Authenticate
with GitHub CLI, a credential manager, or a personal access token when Git asks.
Never put a token in a script, committed file, or remote URL.

Before starting work on another machine or VM:

```bash
git pull --rebase
```

After a meaningful change:

```bash
git status
git add suites/optimized results README.md prompts.txt scripts
git commit -m "Optimize raytrace intersection calculation"
git pull --rebase
git push
```

Use focused commit messages. For example:

```text
Add baseline raytrace measurements
Optimize ray-sphere intersection
Add optimized raytrace profiling results
Document hardware acceleration interface
```

The repository intentionally ignores virtual environments, downloaded vendor
repositories, raw `perf.data`, and intermediate stack files. It keeps the
source changes, timing JSON, text reports, comparisons, and flame graphs that
are useful for the assignment and version history.

## If `perf` is blocked

First check:

```bash
perf --version
cat /proc/sys/kernel/perf_event_paranoid
```

In a course-owned VM, run the project script with the permissions recommended
by the course staff. If `perf` says that tools for the current kernel are
missing, install the exact package it prints; Ubuntu kernel package names vary
between images.

## Fair-comparison checklist

- Run both versions in the same VM and with the same interpreter.
- Close unrelated workloads.
- Do not change benchmark input size between versions.
- Validate correctness before claiming a speedup.
- Commit the original copy before modifying the optimized copy.
- Keep `prompts.txt` updated because the assignment requires AI prompts.
- Treat at least 7% as the project target, but also inspect whether the
  comparison reports statistical significance.



## HERE

```bash
cd 0460882-Project-HwiSwiCoDesign

gh auth login
gh auth status

#this is to avoid conflicts
git status
git pull --ff-only #-ffmeans “download the GitHub updates only if they can be applied cleanly.” It avoids Git unexpectedly creating a merge commit. 
#download changes + integrate them ONLY if Git can do it without creating a merge or rebase
#./scripts/run_one.sh raytrace original full #RUN THIS ONCE - FOR INITIAL RESULTS - DONT NEE TO RUN AGAIN
./scripts/run_one.sh pyflate optimized #full
./scripts/run_one.sh pyflate optimized --fast #less iteration faster than the first #full
./scripts/compare.sh pyflate

git status
#git add results/pyflate/
#or
git add . #this adds all updated files

git status #show you what has been changed
git -c user.name="Yuval" -c user.email="74929281+yuval67@users.noreply.github.com" commit -m "CHANGE ME FOR WHAT UR COMMIT DOES"

#git log -1 --format='%h | %an <%ae> | %s'
git log -1 --format=fuller #Check the identity before pushing - Do this before every push. If the identity is wrong, do not push yet.
git push

gh auth logout #This will logout of all github accounts on the server
gh auth status
```