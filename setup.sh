#!/usr/bin/env bash

set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib.sh
source "${ROOT}/scripts/lib.sh"

cd "${PROJECT_ROOT}"
ensure_env_file
find_python
find_npm

if [[ ! -x "${PROJECT_ROOT}/.venv/bin/python" && \
      ! -x "${PROJECT_ROOT}/.venv/Scripts/python.exe" ]]; then
  echo "Creating Python virtual environment..."
  "${PYTHON[@]}" -m venv .venv
  find_python
fi

echo "Installing Python dependencies..."
"${PYTHON[@]}" -m pip install --upgrade pip
"${PYTHON[@]}" -m pip install -r requirements.lock
"${PYTHON[@]}" -m pip install --no-deps -e .

echo "Installing frontend dependencies..."
(
  cd frontend
  "${NPM[@]}" ci
)

echo
echo "Local dependencies are ready."
echo "Start the container stack with: bash start.sh"
