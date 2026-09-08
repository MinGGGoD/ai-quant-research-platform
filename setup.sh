#!/usr/bin/env bash

set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib.sh
source "${ROOT}/scripts/lib.sh"

cd "${PROJECT_ROOT}"
ensure_env_file
find_uv
find_pnpm

echo "Installing Python dependencies..."
"${UV[@]}" sync --frozen

echo "Installing frontend dependencies..."
(
  cd frontend
  "${PNPM[@]}" install --frozen-lockfile
)

echo
echo "Local dependencies are ready."
echo "Start the container stack with: bash start.sh"
