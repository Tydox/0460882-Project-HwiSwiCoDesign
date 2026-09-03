#!/usr/bin/env bash
set -euo pipefail

echo "================================================="
echo "Configuring kernel permissions for clean profiling..."
echo "================================================="
sudo sysctl -w kernel.kptr_restrict=0
sudo sysctl -w kernel.perf_event_paranoid=-1
echo "Kernel configuration successful!"
echo ""
if [[ $# -lt 2 || $# -gt 3 ]]; then
  printf 'Usage: %s <benchmark> <original|optimized> [--fast]\n' "$0" >&2
  exit 2
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BENCHMARK="$1"
IMPLEMENTATION="$2"
RUN_MODE="standard"
RUN_OPTIONS=()

case "$IMPLEMENTATION" in
  original|optimized) ;;
  *) printf 'Implementation must be original or optimized.\n' >&2; exit 2 ;;
esac

if [[ $# -eq 3 ]]; then
  if [[ "$3" != "--fast" ]]; then
    printf 'Optional third argument must be --fast.\n' >&2
    exit 2
  fi
  RUN_MODE="fast"
  RUN_OPTIONS=(--fast)
fi

MANIFEST="$PROJECT_DIR/suites/$IMPLEMENTATION/MANIFEST"
SOURCE="$PROJECT_DIR/suites/$IMPLEMENTATION/bm_$BENCHMARK/run_benchmark.py"
RESULT_PARENT="$PROJECT_DIR/results/$BENCHMARK/$IMPLEMENTATION"
PYTHON="$PROJECT_DIR/.venv/bin/python"
DEBUG_PYTHON="$PROJECT_DIR/.venv-dbg/bin/python"
FLAMEGRAPH_DIR="$PROJECT_DIR/vendor/FlameGraph"

# pyperformance stores its managed benchmark environments relative to the
# current directory. Keep them inside this project regardless of where the
# script was invoked.
cd "$PROJECT_DIR"

for required in "$MANIFEST" "$SOURCE" "$PYTHON" "$DEBUG_PYTHON" \
  "$FLAMEGRAPH_DIR/stackcollapse-perf.pl" "$FLAMEGRAPH_DIR/flamegraph.pl"; do
  if [[ ! -e "$required" ]]; then
    printf 'Required path is missing: %s\n' "$required" >&2
    exit 1
  fi
done

if [[ "$IMPLEMENTATION" == "optimized" ]]; then
  RUN_TIMESTAMP="$(date '+%Y-%m-%d-%H-%M')"
  RESULT_DIR="$RESULT_PARENT/$RUN_TIMESTAMP"
  if [[ -e "$RESULT_DIR" ]]; then
    printf 'An optimized run already exists for this minute: %s\n' \
      "$RESULT_DIR" >&2
    printf '%s\n' 'Wait until the next minute so no previous run is overwritten.' >&2
    exit 1
  fi
  mkdir -p "$RESULT_DIR"
else
  RESULT_DIR="$RESULT_PARENT"
  mkdir -p "$RESULT_DIR"
fi

TIMING_JSON="$RESULT_DIR/timing.json"
PERF_DATA="$RESULT_DIR/perf.data"
PERF_REPORT="$RESULT_DIR/perf_report.txt"
PERF_SCRIPT="$RESULT_DIR/perf_script.txt"
FOLDED="$RESULT_DIR/stacks.folded"
FLAMEGRAPH="$RESULT_DIR/flamegraph.svg"
RUN_METADATA="$RESULT_DIR/run_metadata.txt"

if git -C "$PROJECT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  GIT_COMMIT="$(git -C "$PROJECT_DIR" rev-parse HEAD 2>/dev/null || printf 'no-commit')"
  if [[ -n "$(git -C "$PROJECT_DIR" status --porcelain)" ]]; then
    GIT_WORKTREE_STATE="dirty"
  else
    GIT_WORKTREE_STATE="clean"
  fi
else
  GIT_COMMIT="not-a-git-repository"
  GIT_WORKTREE_STATE="not-a-git-repository"
fi

rm -f "$TIMING_JSON" "$PERF_DATA" "$PERF_REPORT" "$PERF_SCRIPT" "$FOLDED" "$FLAMEGRAPH" "$RUN_METADATA"

if [[ "$BENCHMARK" == "raytrace" ]]; then
  RAYTRACE_IMAGE="$RESULT_DIR/raytrace.ppm"
  rm -f "$RAYTRACE_IMAGE"
fi

printf 'Timing %s (%s, %s mode)...\n' "$BENCHMARK" "$IMPLEMENTATION" "$RUN_MODE"
"$PYTHON" -m pyperformance run --manifest "$MANIFEST" --benchmarks "$BENCHMARK" "${RUN_OPTIONS[@]}" --output "$TIMING_JSON"

printf 'Profiling one representative %s value (%s) with debug Python...\n' "$BENCHMARK" "$IMPLEMENTATION"
perf record -F 999 -e cpu-clock -g --output "$PERF_DATA" -- "$DEBUG_PYTHON" -m pyperformance run --manifest "$MANIFEST" --benchmarks "$BENCHMARK" --debug-single-value

printf 'Creating perf report...\n'
perf report --stdio --input "$PERF_DATA" > "$PERF_REPORT"
if ! grep -q '%' "$PERF_REPORT"; then
  printf 'perf report did not produce any sample rows: %s\n' "$PERF_REPORT" >&2
  exit 1
fi
printf 'Exporting and collapsing perf stacks...\n'
perf script --input "$PERF_DATA" > "$PERF_SCRIPT"
"$FLAMEGRAPH_DIR/stackcollapse-perf.pl" "$PERF_SCRIPT" > "$FOLDED"
if [[ ! -s "$FOLDED" ]]; then
  printf 'No stack samples were produced: %s\n' "$FOLDED" >&2
  exit 1
fi
printf 'Creating flame graph...\n'
"$FLAMEGRAPH_DIR/flamegraph.pl" --title "$BENCHMARK - $IMPLEMENTATION" "$FOLDED" > "$FLAMEGRAPH"

# Raytrace already supports --filename. Render one representative image in a
# separate invocation so file output is not included in the measured timing or
# in the perf profile.
if [[ "$BENCHMARK" == "raytrace" ]]; then
  printf 'Saving Raytrace image: %s\n' "$RAYTRACE_IMAGE"
  "$PYTHON" "$SOURCE" --debug-single-value --filename "$RAYTRACE_IMAGE"
fi

{
  printf 'benchmark=%s\n' "$BENCHMARK"
  printf 'implementation=%s\n' "$IMPLEMENTATION"
  printf 'completed_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'source_sha256=%s\n' "$(sha256sum "$SOURCE" | cut -d ' ' -f 1)"
  printf 'git_commit=%s\n' "$GIT_COMMIT"
  printf 'git_worktree=%s\n' "$GIT_WORKTREE_STATE"
  if [[ "$BENCHMARK" == "raytrace" ]]; then
    printf '%s\n' 'raytrace_image=raytrace.ppm'
  fi
} > "$RUN_METADATA"

if [[ "$IMPLEMENTATION" == "optimized" ]]; then
  ln -sfn "$RUN_TIMESTAMP" "$RESULT_PARENT/latest"
fi

printf 'Finished. Results: %s\n' "$RESULT_DIR"
