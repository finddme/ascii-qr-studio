#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "$0")" && pwd)"
export ASCII_UID="$(id -u)" ASCII_GID="$(id -g)"
mkdir -p "$ROOT/dev"
docker compose -f "$ROOT/compose.yaml" up -d --build --wait web
echo 'ASCII QR Studio: http://localhost:8787'
