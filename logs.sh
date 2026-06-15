#!/usr/bin/env bash

set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib.sh
source "${ROOT}/scripts/lib.sh"
find_docker
require_docker_running

cd "${PROJECT_ROOT}"

if [[ $# -gt 1 ]]; then
  echo "Usage: bash logs.sh [postgres|backend|frontend]" >&2
  exit 2
fi

if [[ $# -eq 1 ]]; then
  compose logs --follow --tail=200 "$1"
else
  compose logs --follow --tail=200 postgres backend frontend
fi
