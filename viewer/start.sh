#!/usr/bin/env bash
set -euo pipefail
stage09_viewer_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$stage09_viewer_dir/../scripts/stage09_server.py" "$@"
