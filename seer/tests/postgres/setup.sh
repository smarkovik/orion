#!/usr/bin/env bash
# Postgres + pgvector for Seer prototypes. Usage: ./setup.sh [up|down]
set -euo pipefail

IMAGE="pgvector/pgvector:0.8.7-pg16"
NAME="${SEER_PG_CONTAINER:-seer-pg}"
PORT="${SEER_PG_PORT:-5432}"
PASSWORD="${SEER_PG_PASSWORD:-seer}"
DB="seer"

ensure_docker() {
  # Wait out a dockerd that is still starting or shutting down.
  for _ in $(seq 1 15); do
    docker info >/dev/null 2>&1 && return
    pgrep -x dockerd >/dev/null || break
    sleep 1
  done
  # Cloud sessions ship dockerd without starting it.
  if command -v dockerd >/dev/null && [ "$(id -u)" = 0 ]; then
    echo "Starting dockerd..."
    (dockerd >"${TMPDIR:-/tmp}/dockerd.log" 2>&1 &)
    for _ in $(seq 1 30); do
      docker info >/dev/null 2>&1 && return
      sleep 1
    done
  fi
  echo "Docker daemon not available" >&2
  exit 1
}

up() {
  ensure_docker
  if docker ps -a --format '{{.Names}}' | grep -qx "$NAME"; then
    docker start "$NAME" >/dev/null
  else
    docker run -d --name "$NAME" -e POSTGRES_PASSWORD="$PASSWORD" -e POSTGRES_DB="$DB" \
      -p "$PORT:5432" "$IMAGE" >/dev/null
  fi
  # TCP check: the image's init-time server listens on the socket only.
  for _ in $(seq 1 60); do
    if docker exec "$NAME" pg_isready -h 127.0.0.1 -U postgres -d "$DB" >/dev/null 2>&1; then
      docker exec "$NAME" psql -h 127.0.0.1 -U postgres -d "$DB" -qc "SET client_min_messages = warning; CREATE EXTENSION IF NOT EXISTS vector;"
      echo "postgresql://postgres:${PASSWORD}@localhost:${PORT}/${DB}"
      return
    fi
    sleep 1
  done
  echo "Postgres did not become ready" >&2
  exit 1
}

down() {
  docker rm -f "$NAME" >/dev/null 2>&1 || true
}

case "${1:-up}" in
  up) up ;;
  down) down ;;
  *) echo "Usage: $0 [up|down]" >&2; exit 1 ;;
esac
