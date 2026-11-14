#!/usr/bin/env bash
# Cluster prototype. Usage: ./run.sh [all|up|scrape|cluster|down]
set -euo pipefail
cd "$(dirname "$0")"

FILES=(-f docker-compose.yml)
if [ -n "${HTTPS_PROXY:-}" ]; then
  FILES+=(-f docker-compose.proxy.yml)
  for ca in "${SSL_CERT_FILE:-}" /root/.ccr/ca-bundle.crt; do
    if [ -n "$ca" ] && [ -f "$ca" ]; then cp "$ca" certs/extra-ca.crt; break; fi
  done
fi

ensure_docker() {
  docker info >/dev/null 2>&1 && return
  # Cloud sessions ship dockerd without starting it.
  if command -v dockerd >/dev/null && [ "$(id -u)" = 0 ]; then
    (dockerd >"${TMPDIR:-/tmp}/dockerd.log" 2>&1 &)
    for _ in $(seq 1 30); do docker info >/dev/null 2>&1 && return; sleep 1; done
  fi
  echo "Docker daemon not available" >&2
  exit 1
}

dc() { docker compose "${FILES[@]}" "$@"; }

ensure_docker
case "${1:-all}" in
  up) dc up -d --build db viewer ;;
  scrape) dc run --rm --build scraper ;;
  cluster) dc run --rm --build clusterer ;;
  all)
    dc up -d --build db viewer
    dc run --rm --build scraper
    dc run --rm --build clusterer
    echo "Viewer: http://localhost:8080"
    ;;
  down) dc down ;;
  *) echo "Usage: $0 [all|up|scrape|cluster|down]" >&2; exit 1 ;;
esac
