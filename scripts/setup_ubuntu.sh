#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENDOR_DIR="$PROJECT_DIR/vendor"

sudo apt-get update
sudo apt-get install -y \
  git \
  perl \
  python3.12 \
  python3.12-dbg \
  python3.12-dev \
  python3.12-venv \
  python3-pip \
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

NORMAL_ENV="$PROJECT_DIR/.venv312"
DEBUG_ENV="$PROJECT_DIR/.venv312-dbg"

python3.12 -m venv "$NORMAL_ENV"
"$NORMAL_ENV/bin/python" -m pip install --upgrade pip
"$NORMAL_ENV/bin/python" -m pip install -e "$VENDOR_DIR/pyperformance"
"$NORMAL_ENV/bin/python" -m pip install 'numpy>=1.24,<3'

if python3.12-dbg -m venv "$DEBUG_ENV"; then
  "$DEBUG_ENV/bin/python" -m pip install --upgrade pip
  "$DEBUG_ENV/bin/python" -m pip install -e "$VENDOR_DIR/pyperformance"
  "$DEBUG_ENV/bin/python" -m pip install 'numpy>=1.24,<3'
else
  printf '%s\n' \
    'Could not create the Python 3.12 debug virtual environment.' \
    'Profiling needs python3.12-dbg with venv support.' >&2
  exit 1
fi

"$NORMAL_ENV/bin/python" -c \
  'import sys; assert sys.version_info[:2] == (3, 12), sys.version'
"$DEBUG_ENV/bin/python" -c '
import sys
import sysconfig
assert sys.version_info[:2] == (3, 12), sys.version
assert sysconfig.get_config_var("Py_DEBUG") == 1
sys.activate_stack_trampoline("perf")
sys.deactivate_stack_trampoline()
'
"$NORMAL_ENV/bin/python" -m pyperformance --help >/dev/null
"$DEBUG_ENV/bin/python" -m pyperformance --help >/dev/null
perf --version

printf '%s\n' \
  'Setup complete.' \
  "Normal Python: $NORMAL_ENV/bin/python" \
  "Debug Python:  $DEBUG_ENV/bin/python"

