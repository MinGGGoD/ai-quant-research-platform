#!/usr/bin/env bash

set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib.sh
source "${ROOT}/scripts/lib.sh"
find_docker
ensure_docker_running

if [[ $# -eq 0 ]]; then
  echo "Usage: bash scanner.sh <scanner arguments>" >&2
  echo "Example: bash scanner.sh --help" >&2
  exit 2
fi

cd "${PROJECT_ROOT}"
ensure_env_file
compose up -d postgres
wait_for_service postgres
compose --profile tools run --rm scanner "$@"
