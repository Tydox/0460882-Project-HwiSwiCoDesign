#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  printf 'Usage: %s <benchmark-name>\n' "$0" >&2
  exit 2
fi

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BENCHMARK="$1"
SOURCE_DIR="$PROJECT_DIR/vendor/pyperformance/pyperformance/data-files/benchmarks/bm_$BENCHMARK"

if [[ ! -d "$SOURCE_DIR" ]]; then
  printf 'Benchmark source not found: %s\n' "$SOURCE_DIR" >&2
  printf '%s\n' 'Run scripts/setup_ubuntu.sh first and verify the benchmark name.' >&2
  exit 1
fi

for implementation in original optimized; do
  DESTINATION="$PROJECT_DIR/suites/$implementation/bm_$BENCHMARK"
  if [[ -e "$DESTINATION" ]]; then
    printf 'Refusing to overwrite existing directory: %s\n' "$DESTINATION" >&2
    exit 1
  fi
  mkdir -p "$(dirname "$DESTINATION")"
  cp -a "$SOURCE_DIR" "$DESTINATION"

  # Upstream benchmarks inherit the suite version from pyperformance itself.
  # A standalone custom suite has no such parent, so make the copied metadata
  # self-contained.
  sed -i 's/^dynamic = \["version"\]$/version = "1.0"/' \
    "$DESTINATION/pyproject.toml"
done

"$PROJECT_DIR/scripts/refresh_manifests.sh"

printf 'Added %s. Edit only suites/optimized/bm_%s/run_benchmark.py\n' \
  "$BENCHMARK" "$BENCHMARK"
