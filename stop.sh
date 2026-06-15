#!/usr/bin/env bash

set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib.sh
source "${ROOT}/scripts/lib.sh"
find_docker

cd "${PROJECT_ROOT}"
if ! docker_is_running; then
  echo "Docker Desktop is not running; there are no active containers to stop."
  exit 0
fi
compose down
echo "Services stopped. The PostgreSQL data volume was preserved."
