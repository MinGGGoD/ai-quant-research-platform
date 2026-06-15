#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${PROJECT_ROOT}/deployment/compose.yaml"

is_wsl() {
  [[ -n "${WSL_INTEROP:-}" ]] || grep -qi microsoft /proc/version 2>/dev/null
}

find_docker() {
  local windows_docker

  if is_wsl; then
    windows_docker="/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe"
    if [[ -x "${windows_docker}" ]]; then
      DOCKER=("${windows_docker}")
      DOCKER_USES_WINDOWS_PATHS=true
      return
    fi
  fi

  if command -v docker >/dev/null 2>&1; then
    DOCKER=(docker)
    return
  fi

  windows_docker="/c/Program Files/Docker/Docker/resources/bin/docker.exe"
  if [[ -x "${windows_docker}" ]]; then
    DOCKER=("${windows_docker}")
    return
  fi

  echo "Docker CLI was not found. Install or start Docker Desktop." >&2
  exit 1
}

compose() {
  local compose_file="${COMPOSE_FILE}"
  if [[ "${DOCKER_USES_WINDOWS_PATHS:-false}" == true ]]; then
    compose_file="$(wslpath -w "${compose_file}")"
  fi
  "${DOCKER[@]}" compose -f "${compose_file}" "$@"
}

docker_is_running() {
  "${DOCKER[@]}" info >/dev/null 2>&1
}

start_docker_desktop() {
  local windows_desktop="C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe"
  local desktop_candidates=(
    "/c/Program Files/Docker/Docker/Docker Desktop.exe"
    "/mnt/c/Program Files/Docker/Docker/Docker Desktop.exe"
  )
  local candidate

  for candidate in "${desktop_candidates[@]}"; do
    if [[ ! -f "${candidate}" ]]; then
      continue
    fi

    echo "Starting Docker Desktop..."
    if command -v powershell.exe >/dev/null 2>&1; then
      powershell.exe -NoProfile -NonInteractive -Command \
        "Start-Process -FilePath '${windows_desktop}'" >/dev/null 2>&1
    else
      "${candidate}" >/dev/null 2>&1 &
    fi
    return 0
  done

  return 1
}

ensure_docker_running() {
  if docker_is_running; then
    return
  fi

  if start_docker_desktop; then
    local elapsed=0
    while ((elapsed < 180)); do
      if docker_is_running; then
        echo "Docker Desktop is ready."
        return
      fi
      sleep 3
      elapsed=$((elapsed + 3))
    done
  fi

  echo "Docker is installed but its daemon is not running." >&2
  echo "Start Docker Desktop, wait for the engine to become ready, and try again." >&2
  exit 1
}

require_docker_running() {
  if ! docker_is_running; then
    echo "Docker Desktop is not running." >&2
    exit 1
  fi
}

ensure_env_file() {
  if [[ ! -f "${PROJECT_ROOT}/.env" ]]; then
    cp "${PROJECT_ROOT}/.env.example" "${PROJECT_ROOT}/.env"
    echo "Created .env from .env.example."
  fi
}

wait_for_service() {
  local service="$1"
  local timeout_seconds="${2:-120}"
  local elapsed=0
  local container_id
  local status

  while ((elapsed < timeout_seconds)); do
    container_id="$(compose ps -q "${service}")"
    if [[ -n "${container_id}" ]]; then
      status="$("${DOCKER[@]}" inspect \
        --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
        "${container_id}" 2>/dev/null || true)"
      if [[ "${status}" == "healthy" || "${status}" == "running" ]]; then
        echo "${service} is ${status}."
        return
      fi
      if [[ "${status}" == "unhealthy" || "${status}" == "exited" ]]; then
        echo "${service} entered state: ${status}" >&2
        compose logs --tail=100 "${service}" >&2
        exit 1
      fi
    fi

    sleep 2
    elapsed=$((elapsed + 2))
  done

  echo "Timed out waiting for ${service}." >&2
  compose logs --tail=100 "${service}" >&2
  exit 1
}

find_python() {
  local candidates=(
    "${PROJECT_ROOT}/.venv/bin/python"
    "${PROJECT_ROOT}/.venv/Scripts/python.exe"
  )
  local candidate

  for candidate in "${candidates[@]}"; do
    if [[ -x "${candidate}" ]]; then
      PYTHON=("${candidate}")
      if is_wsl && [[ "${candidate}" == *.exe ]]; then
        PYTHON_USES_WINDOWS_PATHS=true
      fi
      return
    fi
  done

  if command -v python3.11 >/dev/null 2>&1; then
    PYTHON=(python3.11)
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON=(python3)
  elif command -v python >/dev/null 2>&1; then
    PYTHON=(python)
  elif command -v py >/dev/null 2>&1; then
    PYTHON=(py -3.11)
  else
    echo "Python 3.11-3.13 was not found." >&2
    exit 1
  fi
}

find_npm() {
  if is_wsl && command -v cmd.exe >/dev/null 2>&1; then
    NPM=(cmd.exe /d /c npm.cmd)
  elif command -v npm >/dev/null 2>&1; then
    NPM=(npm)
  else
    echo "npm was not found. Install Node.js and npm." >&2
    exit 1
  fi
}
