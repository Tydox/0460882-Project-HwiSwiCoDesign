#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RESULTS_DIR="$PROJECT_DIR/results"
REMOTE_DESTINATION="${REMOTE_DESTINATION:-ece882-011@10.0.2.2:~/}"

if [[ ! -d "$RESULTS_DIR" ]]; then
  printf 'Results directory does not exist: %s\n' "$RESULTS_DIR" >&2
  exit 1
fi

if [[ -z "$(find "$RESULTS_DIR" -mindepth 1 -print -quit)" ]]; then
  printf 'Results directory is empty: %s\n' "$RESULTS_DIR" >&2
  exit 1
fi

printf 'Copying the complete results folder to %s\n' "$REMOTE_DESTINATION"
scp -r "$RESULTS_DIR" "$REMOTE_DESTINATION"
printf '%s\n' 'Upload complete. Remote folder: ~/results'

