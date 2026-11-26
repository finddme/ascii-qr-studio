#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "$0")" && pwd)"
export ASCII_UID="$(id -u)" ASCII_GID="$(id -g)"
mkdir -p "$ROOT/dev"
exec docker compose -f "$ROOT/compose.yaml" run --build --quiet-build --rm -T --no-deps cli python -m unittest -v
