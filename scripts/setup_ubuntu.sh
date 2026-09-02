#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENDOR_DIR="$PROJECT_DIR/vendor"

sudo apt-get update
sudo apt-get install -y \
  git \
  perl \
  python3 \
  python3-dbg \
  python3-dev \
  python3-pip \
  python3-venv \
  linux-tools-common \
  linux-tools-generic

mkdir -p "$VENDOR_DIR" "$PROJECT_DIR/results"

if [[ ! -d "$VENDOR_DIR/pyperformance/.git" ]]; then
  git clone --depth 1 https://github.com/python/pyperformance.git \
    "$VENDOR_DIR/pyperformance"
fi

if [[ ! -d "$VENDOR_DIR/FlameGraph/.git" ]]; then
  git clone --depth 1 https://github.com/brendangregg/FlameGraph.git \
    "$VENDOR_DIR/FlameGraph"
fi

python3 -m venv "$PROJECT_DIR/.venv"
"$PROJECT_DIR/.venv/bin/python" -m pip install --upgrade pip
"$PROJECT_DIR/.venv/bin/python" -m pip install -e "$VENDOR_DIR/pyperformance"

if python3-dbg -m venv "$PROJECT_DIR/.venv-dbg"; then
  "$PROJECT_DIR/.venv-dbg/bin/python" -m pip install --upgrade pip
  "$PROJECT_DIR/.venv-dbg/bin/python" -m pip install -e "$VENDOR_DIR/pyperformance"
else
  printf '%s\n' \
    'Could not create the debug-Python virtual environment.' \
    'Timing will work, but profiling needs python3-dbg with venv support.' >&2
  exit 1
fi

"$PROJECT_DIR/.venv/bin/python" -m pyperformance --help >/dev/null
"$PROJECT_DIR/.venv-dbg/bin/python" -m pyperformance --help >/dev/null
perf --version

printf '%s\n' 'Setup complete.'

