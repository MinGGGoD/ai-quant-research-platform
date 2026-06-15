#!/usr/bin/env bash

set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib.sh
source "${ROOT}/scripts/lib.sh"
find_docker
ensure_docker_running

cd "${PROJECT_ROOT}"
ensure_env_file
compose up -d postgres
wait_for_service postgres
compose run --rm backend alembic upgrade head
compose run --rm backend alembic current
