#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for implementation in original optimized; do
  SUITE_DIR="$PROJECT_DIR/suites/$implementation"
  mkdir -p "$SUITE_DIR"
  MANIFEST_TMP="$SUITE_DIR/MANIFEST.tmp"

  {
    printf '%s\n' '[benchmarks]'
    printf '\n'
    printf 'name\tmetafile\n'
    shopt -s nullglob
    for benchmark_dir in "$SUITE_DIR"/bm_*; do
      benchmark_name="$(basename "$benchmark_dir")"
      benchmark_name="${benchmark_name#bm_}"
      printf '%s\t%s\n' "$benchmark_name" '<local>'

      for variant_file in "$benchmark_dir"/bm_*.toml; do
        variant_name="$(basename "$variant_file" .toml)"
        variant_name="${variant_name#bm_}"
        printf '%s\t<local:%s>\n' "$variant_name" "$benchmark_name"
      done
    done
  } > "$MANIFEST_TMP"

  mv "$MANIFEST_TMP" "$SUITE_DIR/MANIFEST"
done
