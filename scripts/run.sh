#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ENGINE="$1"
shift
export ASCII_UID="$(id -u)" ASCII_GID="$(id -g)"
mkdir -p "$ROOT/dev/output"
if [[ $# -eq 0 || "$1" == --help || "$1" == -h ]]; then
  exec docker compose -f "$ROOT/compose.yaml" run --build --quiet-build --rm -T --no-deps cli python "$ENGINE" --help
fi
INPUT="$(realpath -- "$1")"
[[ -f "$INPUT" && "$INPUT" != *:* ]] || { echo 'Input file missing or unsupported path.' >&2; exit 2; }
shift
echo "Results: $ROOT/dev/output" >&2
exec docker compose -f "$ROOT/compose.yaml" run --build --quiet-build --rm -T --no-deps \
  --volume "$INPUT:/input/$(basename -- "$INPUT"):ro" \
  cli python "$ENGINE" "/input/$(basename -- "$INPUT")" "$@"
