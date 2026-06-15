#!/usr/bin/env bash

set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/lib.sh
source "${ROOT}/scripts/lib.sh"

target="${1:-all}"
if [[ "${target}" != "all" && "${target}" != "python" && "${target}" != "frontend" ]]; then
  echo "Usage: bash test.sh [all|python|frontend]" >&2
  exit 2
fi

cd "${PROJECT_ROOT}"

if [[ "${target}" == "all" || "${target}" == "python" ]]; then
  find_python
  echo "Running Python checks..."
  "${PYTHON[@]}" -m ruff check .
  "${PYTHON[@]}" -m ruff format --check .
  "${PYTHON[@]}" -m mypy ai backend rag scanner
  (
    test_workdir="$(mktemp -d "${PROJECT_ROOT}/.pytest-run.XXXXXX")"
    alembic_script_location="${PROJECT_ROOT}/backend/alembic"
    pytest_config="${PROJECT_ROOT}/pyproject.toml"
    pytest_cache="${PROJECT_ROOT}/.pytest_cache"
    pytest_backend="${PROJECT_ROOT}/backend/tests"
    pytest_scanner="${PROJECT_ROOT}/scanner/tests"
    pytest_cross_module="${PROJECT_ROOT}/tests"
    python_path="${PROJECT_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

    if [[ "${PYTHON_USES_WINDOWS_PATHS:-false}" == true ]]; then
      alembic_script_location="$(wslpath -m "${alembic_script_location}")"
      pytest_config="$(wslpath -m "${pytest_config}")"
      pytest_cache="$(wslpath -m "${pytest_cache}")"
      pytest_backend="$(wslpath -m "${pytest_backend}")"
      pytest_scanner="$(wslpath -m "${pytest_scanner}")"
      pytest_cross_module="$(wslpath -m "${pytest_cross_module}")"
      python_path="$(wslpath -m "${PROJECT_ROOT}")"
    elif command -v cygpath >/dev/null 2>&1; then
      alembic_script_location="$(cygpath -m "${alembic_script_location}")"
    fi
    awk -v script_location="${alembic_script_location}" \
      '/^script_location = / { print "script_location = " script_location; next } { print }' \
      "${PROJECT_ROOT}/alembic.ini" >"${test_workdir}/alembic.ini"

    cleanup_test_workdir() {
      rm -f "${test_workdir}/alembic.ini"
      rmdir "${test_workdir}" 2>/dev/null || true
    }
    trap cleanup_test_workdir EXIT

    cd "${test_workdir}"
    PYTHONPATH="${python_path}" \
      "${PYTHON[@]}" -m pytest \
      -c "${pytest_config}" \
      -o "cache_dir=${pytest_cache}" \
      "${pytest_backend}" \
      "${pytest_scanner}" \
      "${pytest_cross_module}"
  )
fi

if [[ "${target}" == "all" || "${target}" == "frontend" ]]; then
  find_npm
  echo "Running frontend checks..."
  (
    cd frontend
    "${NPM[@]}" run format:check
    "${NPM[@]}" run lint
    "${NPM[@]}" run typecheck
    "${NPM[@]}" test
    "${NPM[@]}" run build
  )
fi
