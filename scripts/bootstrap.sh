#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_CACHE_DIR="$PWD/work/cache/uv"
mkdir -p "$UV_CACHE_DIR"
if [ ! -x .venv/bin/python ]; then uv venv --python python3 .venv; fi
uv pip sync --python .venv/bin/python requirements.lock
.venv/bin/python scripts/project.py env
