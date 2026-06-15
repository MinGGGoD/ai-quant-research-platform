#!/usr/bin/env bash

set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib.sh
source "${ROOT}/scripts/lib.sh"
find_docker
ensure_docker_running

build=true
if [[ "${1:-}" == "--no-build" ]]; then
  build=false
elif [[ $# -gt 0 ]]; then
  echo "Usage: bash start.sh [--no-build]" >&2
  exit 2
fi

cd "${PROJECT_ROOT}"
ensure_env_file
compose config >/dev/null

if [[ "${build}" == true ]]; then
  echo "Building backend and frontend images..."
  compose build backend frontend
fi

echo "Starting PostgreSQL..."
compose up -d postgres
wait_for_service postgres

echo "Applying database migrations..."
compose run --rm backend alembic upgrade head

echo "Starting backend and frontend..."
compose up -d backend frontend
wait_for_service backend
wait_for_service frontend

echo
echo "AI Quant Research Platform is running."
frontend_address="$(compose port frontend 5173 | tail -n 1)"
backend_address="$(compose port backend 8000 | tail -n 1)"
echo "Dashboard: http://localhost:${frontend_address##*:}"
echo "API docs:  http://localhost:${backend_address##*:}/docs"
echo "Status:    bash status.sh"
echo "Logs:      bash logs.sh"
