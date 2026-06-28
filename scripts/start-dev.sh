#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-8199}"
if [[ "${1:-}" == "-Port" || "${1:-}" == "--port" ]]; then
  PORT="${2:-8199}"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$SCRIPT_DIR/start-dev.ps1" -Port "$PORT"
