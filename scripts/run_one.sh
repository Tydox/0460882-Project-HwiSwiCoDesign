#!/usr/bin/env bash
set -euo pipefail

# Keep perf diagnostics and counter formatting predictable across VM locales.
export LC_ALL=C

if [[ $# -lt 2 ]]; then
  printf 'Usage: %s <benchmark> <original|optimized> [--fast|--debug-single-value] [--width PIXELS] [--height PIXELS] [--batch-size RAYS]\n' "$0" >&2
  exit 2
fi

BENCHMARK="$1"
IMPLEMENTATION="$2"
shift 2
RUN_MODE="regular"
RUN_OPTIONS=()
BENCHMARK_OPTIONS=()
RAYTRACE_WIDTH=100
RAYTRACE_HEIGHT=100
RAYTRACE_BATCH_SIZE=""

case "$IMPLEMENTATION" in
  original|optimized) ;;
  *) printf 'Implementation must be original or optimized.\n' >&2; exit 2 ;;
esac

while [[ $# -gt 0 ]]; do
  case "$1" in
    --fast|--debug-single-value)
      if [[ ${#RUN_OPTIONS[@]} -ne 0 ]]; then
        printf 'Choose only one mode: --fast or --debug-single-value.\n' >&2
        exit 2
      fi
      RUN_OPTIONS=("$1")
      if [[ "$1" == "--fast" ]]; then RUN_MODE="fast"; else RUN_MODE="debug-single-value"; fi
      shift
      ;;
    --width|--height)
      if [[ "$BENCHMARK" != "raytrace" ]]; then
        printf '%s is supported only for the raytrace benchmark.\n' "$1" >&2
        exit 2
      fi
      if [[ $# -lt 2 || ! "$2" =~ ^[1-9][0-9]*$ ]]; then
        printf '%s requires a positive integer.\n' "$1" >&2
        exit 2
      fi
      if [[ "$1" == "--width" ]]; then RAYTRACE_WIDTH="$2"; else RAYTRACE_HEIGHT="$2"; fi
      shift 2
      ;;
    --batch-size)
      if [[ "$BENCHMARK" != "raytrace" || "$IMPLEMENTATION" != "optimized" ]]; then
        printf '%s is supported only for optimized raytrace.\n' "$1" >&2
        exit 2
      fi
      RAYTRACE_BATCH_SIZE="$2"
      shift 2
      ;;
    *)
      printf 'Unknown option: %s\n' "$1" >&2
      exit 2
      ;;
  esac
done

if [[ "$BENCHMARK" == "raytrace" ]]; then
  BENCHMARK_OPTIONS=(--width "$RAYTRACE_WIDTH" --height "$RAYTRACE_HEIGHT")
  if [[ -n "$RAYTRACE_BATCH_SIZE" ]]; then
    BENCHMARK_OPTIONS+=(--batch-size "$RAYTRACE_BATCH_SIZE")
  fi
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="$PROJECT_DIR/suites/$IMPLEMENTATION/MANIFEST"
SOURCE="$PROJECT_DIR/suites/$IMPLEMENTATION/bm_$BENCHMARK/run_benchmark.py"
RESULT_PARENT="$PROJECT_DIR/results/$BENCHMARK/$IMPLEMENTATION"
PYTHON="$PROJECT_DIR/.venv312/bin/python"
DEBUG_PYTHON="$PROJECT_DIR/.venv312-dbg/bin/python"
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

echo "================================================="
echo "Configuring kernel permissions for clean profiling..."
echo "================================================="
sudo sysctl -w kernel.kptr_restrict=0
sudo sysctl -w kernel.perf_event_paranoid=-1
echo "Kernel configuration successful!"
echo ""

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
PERF_STAT="$RESULT_DIR/perf_stat.txt"
PERF_EVENTS="$RESULT_DIR/perf_events.txt"
PERF_PROBE_LOG="$RESULT_DIR/perf_probe.log"
PERF_RECORD_LOG="$RESULT_DIR/perf_record.log"
FOLDED="$RESULT_DIR/speedscope.folded"
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

rm -f "$TIMING_JSON" "$PERF_DATA" "$PERF_REPORT" "$PERF_SCRIPT" "$FOLDED" \
  "$RESULT_DIR/stacks.folded" "$FLAMEGRAPH" "$RUN_METADATA" \
  "$PERF_STAT" "$PERF_EVENTS" "$PERF_PROBE_LOG" "$PERF_RECORD_LOG"

if [[ "$BENCHMARK" == "raytrace" ]]; then
  RAYTRACE_IMAGE="$RESULT_DIR/raytrace.ppm"
  rm -f "$RAYTRACE_IMAGE"
fi

# Use exactly the same benchmark arguments for all three measurement passes.
if [[ "$BENCHMARK" == "raytrace" ]]; then
  WORKLOAD=("$SOURCE" "${RUN_OPTIONS[@]}" "${BENCHMARK_OPTIONS[@]}")
else
  WORKLOAD=(-m pyperformance run --manifest "$MANIFEST" --benchmarks "$BENCHMARK" "${RUN_OPTIONS[@]}")
fi

# Aliases (branches/branch-instructions, cycles/cpu-cycles, etc.) count the
# same event, so request only one spelling. Extra generic events are probed
# too: perf list alone does not guarantee the VM exposes the corresponding PMU.
COUNTER_CANDIDATES=(
  cpu-clock task-clock cycles instructions branch-instructions branch-misses
  bus-cycles cache-references cache-misses ref-cycles
  stalled-cycles-frontend stalled-cycles-backend
  page-faults minor-faults major-faults context-switches cpu-migrations
  alignment-faults emulation-faults cgroup-switches
  L1-dcache-loads L1-dcache-load-misses L1-dcache-stores L1-dcache-store-misses
  L1-dcache-prefetches L1-dcache-prefetch-misses
  L1-icache-loads L1-icache-load-misses
  LLC-loads LLC-load-misses LLC-stores LLC-store-misses LLC-prefetches LLC-prefetch-misses
  dTLB-loads dTLB-load-misses dTLB-stores dTLB-store-misses
  iTLB-loads iTLB-load-misses branch-loads branch-load-misses
  node-loads node-load-misses node-stores node-store-misses
  duration_time user_time system_time dummy bpf-output
)
STAT_EVENTS=()
RECORD_EVENTS=()
PROFILE_EVENT=cpu-clock
PROFILE_FREQUENCY=199
PROFILE_CALL_GRAPH=fp
PROBE_DIR="$(mktemp -d "$RESULT_DIR/.perf-probe.XXXXXX")"
trap 'rm -f "$PROBE_DIR/stat.txt" "$PROBE_DIR/record.data" "$PROBE_DIR/record.data.old"; rmdir "$PROBE_DIR"' EXIT
printf 'event\tstat\trecord\n' > "$PERF_EVENTS"
printf 'Probing perf events; diagnostics: %s\n' "$PERF_PROBE_LOG"
for event in "${COUNTER_CANDIDATES[@]}"; do
  printf '\n=== stat: %s ===\n' "$event" >> "$PERF_PROBE_LOG"
  stat_status=unavailable
  if perf stat --no-big-num -e "$event" --output "$PROBE_DIR/stat.txt" -- sleep 0.05 \
      >> "$PERF_PROBE_LOG" 2>&1; then
    # Some perf versions exit successfully even when a counter cannot run.
    if [[ -s "$PROBE_DIR/stat.txt" ]] && ! grep -Eq '<not supported>|<not counted>' "$PROBE_DIR/stat.txt"; then
      stat_status=enabled
    fi
  fi
  if [[ -f "$PROBE_DIR/stat.txt" ]]; then
    cat "$PROBE_DIR/stat.txt" >> "$PERF_PROBE_LOG"
    rm -f "$PROBE_DIR/stat.txt"
  fi

  case "$event" in
    duration_time|user_time|system_time)
      record_status=stat-only
      ;;
    dummy|bpf-output)
      # Probe counting support above, but neither is a benchmark counter:
      # dummy never overflows; bpf-output needs an attached BPF producer.
      stat_status="$stat_status (excluded: special-purpose event)"
      record_status=excluded-special-purpose
      ;;
    *)
      printf '\n=== record: %s ===\n' "$event" >> "$PERF_PROBE_LOG"
      record_status=unavailable
      if sudo perf record -F "$PROFILE_FREQUENCY" --no-bpf-event -e "$event" \
          --call-graph "$PROFILE_CALL_GRAPH" \
          --output "$PROBE_DIR/record.data" -- sleep 0.05 \
          >> "$PERF_PROBE_LOG" 2>&1; then
        record_status=enabled
        RECORD_EVENTS+=("$event")
      fi
      rm -f "$PROBE_DIR/record.data" "$PROBE_DIR/record.data.old"
      ;;
  esac
  if [[ "$stat_status" == enabled ]]; then STAT_EVENTS+=("$event"); fi
  printf '%s\t%s\t%s\n' "$event" "$stat_status" "$record_status" >> "$PERF_EVENTS"
done
if [[ ${#STAT_EVENTS[@]} -eq 0 || ! " ${RECORD_EVENTS[*]} " =~ " $PROFILE_EVENT " ]]; then
  printf 'No usable stat counters or %s sampling unavailable. See %s\n' \
    "$PROFILE_EVENT" "$PERF_PROBE_LOG" >&2
  exit 1
fi
STAT_EVENT_LIST="$(IFS=,; printf '%s' "${STAT_EVENTS[*]}")"
RECORD_EVENT_LIST="$(IFS=,; printf '%s' "${RECORD_EVENTS[*]}")"

printf 'Timing %s (%s, %s mode)...\n' "$BENCHMARK" "$IMPLEMENTATION" "$RUN_MODE"
"$PYTHON" "${WORKLOAD[@]}" --output "$TIMING_JSON"

# Count normal Python in its own pass, without perf record sampling overhead.
# Keep events ungrouped so the kernel can multiplex limited hardware counters.
printf 'Counting %s with perf stat (%s events)...\n' "$BENCHMARK" "${#STAT_EVENTS[@]}"
perf stat --no-big-num -e "$STAT_EVENT_LIST" --output "$PERF_STAT" -- "$PYTHON" "${WORKLOAD[@]}"
if grep -Eq '<not supported>|<not counted>' "$PERF_STAT"; then
  printf 'Some counters could not run together. Check %s for unavailable counts.\n' "$PERF_STAT" >&2
fi

printf 'Profiling %s (%s, %s mode) with debug Python...\n' "$BENCHMARK" "$IMPLEMENTATION" "$RUN_MODE"
# Use one CPU-time sampling event so the report and flame graph have a clear,
# consistent meaning. Python 3.12's perf trampolines expose Python function
# names and are inherited by pyperf workers through PYTHONPERFSUPPORT. Frame
# pointers keep recording compact and stack processing fast. Run perf as root
# so kernel mappings and symbols can be collected when the kernel exposes them.
if ! sudo env PYTHONPERFSUPPORT=1 \
    perf record -F "$PROFILE_FREQUENCY" --no-bpf-event -e "$PROFILE_EVENT" \
    --call-graph "$PROFILE_CALL_GRAPH" --output "$PERF_DATA" -- \
    "$DEBUG_PYTHON" "${WORKLOAD[@]}" \
    --inherit-environ=PYTHONPERFSUPPORT 2> "$PERF_RECORD_LOG"; then
  cat "$PERF_RECORD_LOG" >&2
  exit 1
fi
cat "$PERF_RECORD_LOG" >&2

printf 'Creating perf report...\n'
sudo perf report --stdio --header --show-nr-samples --show-total-period \
  --demangle --percent-limit 0.1 --children \
  --call-graph graph,0.5,caller \
  --sort comm,dso,symbol --input "$PERF_DATA" > "$PERF_REPORT"
if ! grep -q '%' "$PERF_REPORT"; then
  printf 'perf report did not produce any sample rows: %s\n' "$PERF_REPORT" >&2
  exit 1
fi
printf 'Exporting and collapsing perf stacks...\n'
# Keep perf's default stack-depth limit (127 on this server). A lower export
# cap truncates Python 3.12 trampoline-rich callchains before their roots.
sudo perf script -F -period \
  --input "$PERF_DATA" > "$PERF_SCRIPT"
# Omitting perf's period field makes every folded-stack weight one actual
# sample. The compact folded file is directly importable by speedscope.
"$FLAMEGRAPH_DIR/stackcollapse-perf.pl" --event-filter=cpu-clock "$PERF_SCRIPT" > "$FOLDED"
if [[ ! -s "$FOLDED" ]]; then
  printf 'No stack samples were produced: %s\n' "$FOLDED" >&2
  exit 1
fi
printf 'Creating flame graph...\n'
"$FLAMEGRAPH_DIR/flamegraph.pl" --inverted --minwidth 0.1% --hash \
  --title "$BENCHMARK - $IMPLEMENTATION" "$FOLDED" > "$FLAMEGRAPH"

# Raytrace already supports --filename. Render one representative image in a
# separate invocation so file output is not included in the measured timing or
# in the perf profile.
if [[ "$BENCHMARK" == "raytrace" ]]; then
  printf 'Saving Raytrace image: %s\n' "$RAYTRACE_IMAGE"
  "$PYTHON" "$SOURCE" --debug-single-value "${BENCHMARK_OPTIONS[@]}" --filename "$RAYTRACE_IMAGE"
fi

{
  printf 'benchmark=%s\n' "$BENCHMARK"
  printf 'implementation=%s\n' "$IMPLEMENTATION"
  printf 'completed_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'source_sha256=%s\n' "$(sha256sum "$SOURCE" | cut -d ' ' -f 1)"
  printf 'git_commit=%s\n' "$GIT_COMMIT"
  printf 'git_worktree=%s\n' "$GIT_WORKTREE_STATE"
  printf 'run_mode=%s\n' "$RUN_MODE"
  printf 'perf_version=%s\n' "$(perf --version)"
  printf 'kernel=%s\n' "$(uname -r)"
  printf 'perf_stat_python=%s\n' "$PYTHON"
  printf 'perf_record_python=%s\n' "$DEBUG_PYTHON"
  printf 'perf_stat_events=%s\n' "$STAT_EVENT_LIST"
  printf 'perf_record_events=%s\n' "$PROFILE_EVENT"
  printf 'perf_record_available_events=%s\n' "$RECORD_EVENT_LIST"
  printf 'perf_record_frequency=%s\n' "$PROFILE_FREQUENCY"
  printf 'perf_record_call_graph=%s\n' "$PROFILE_CALL_GRAPH"
  printf '%s\n' 'perf_script_max_stack=perf-default'
  printf '%s\n' \
    'python_perf_support=PYTHONPERFSUPPORT=1' \
    'python_perf_support_inherited=PYTHONPERFSUPPORT' \
    'perf_record_kernel_inclusive=true' \
    'perf_report_children=true' \
    'perf_report_call_graph=graph,0.5,caller' \
    'flamegraph_event=cpu-clock' \
    'flamegraph_weight=sample_count' \
    'flamegraph_orientation=icicle' \
    'flamegraph_minwidth=0.1%' \
    'speedscope_file=speedscope.folded'
  if [[ "$BENCHMARK" == "raytrace" ]]; then
    printf '%s\n' 'raytrace_image=raytrace.ppm'
    printf 'raytrace_width=%s\n' "$RAYTRACE_WIDTH"
    printf 'raytrace_height=%s\n' "$RAYTRACE_HEIGHT"
    if [[ "$IMPLEMENTATION" == "optimized" ]]; then
      "$PYTHON" -c 'import json, sys; m = json.load(open(sys.argv[1]))["metadata"]; print("raytrace_batch_size=" + str(m["raytrace_batch_size"])); print("numpy_version=" + m["numpy_version"])' "$TIMING_JSON"
    fi
  fi
} > "$RUN_METADATA"

if [[ "$IMPLEMENTATION" == "optimized" ]]; then
  ln -sfn "$RUN_TIMESTAMP" "$RESULT_PARENT/latest"
fi

printf 'Finished. Results: %s\n' "$RESULT_DIR"
