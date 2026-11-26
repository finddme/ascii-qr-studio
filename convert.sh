#!/usr/bin/env bash
set -euo pipefail
exec "$(dirname -- "$0")/scripts/run.sh" ascii_pipeline.py "$@"
