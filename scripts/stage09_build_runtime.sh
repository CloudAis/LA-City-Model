#!/usr/bin/env bash
set -euo pipefail
stage09_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$stage09_root"
mkdir -p work/logs/stage09
for stage09_step in export overview runtime_optimize terrain_lods overview_lines metadata; do
  .venv/bin/python "scripts/stage09_${stage09_step}.py" > "work/logs/stage09/final_${stage09_step}.log" 2>&1 || {
    stage09_code=$?
    tail -n 10 "work/logs/stage09/final_${stage09_step}.log"
    exit "$stage09_code"
  }
  echo "STAGE09_ACTUAL_${stage09_step}_COMPLETED"
done
