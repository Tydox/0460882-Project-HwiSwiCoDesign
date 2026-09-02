#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  printf 'Usage: %s <benchmark-name>\n' "$0" >&2
  exit 2
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BENCHMARK="$1"
BASELINE="$PROJECT_DIR/results/$BENCHMARK/original/timing.json"
OPTIMIZED_LATEST="$PROJECT_DIR/results/$BENCHMARK/optimized/latest"
CHANGED="$OPTIMIZED_LATEST/timing.json"
COMPARISON="$OPTIMIZED_LATEST/comparison.txt"
PYTHON="$PROJECT_DIR/.venv/bin/python"

if [[ ! -L "$OPTIMIZED_LATEST" || ! -f "$BASELINE" || ! -f "$CHANGED" ]]; then
  printf '%s\n' 'Both original and optimized timing.json files are required.' >&2
  exit 1
fi

"$PYTHON" -m pyperf compare_to \
  "$BASELINE" "$CHANGED" \
  --table \
  | tee "$COMPARISON"

printf 'Comparison saved in: %s\n' "$COMPARISON"
