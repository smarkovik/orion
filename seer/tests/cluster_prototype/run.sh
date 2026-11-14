#!/usr/bin/env bash
# Cluster prototype. Usage: ./run.sh [all|up|scrape|cluster|down]
set -euo pipefail
cd "$(dirname "$0")"

FILES=(-f docker-compose.yml)
PROXY=0
if [ -n "${HTTPS_PROXY:-}" ]; then
  PROXY=1
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

build() {
  if [ "$PROXY" = 1 ]; then
    # Compose's bake builder needs an explicit grant for host-network builds.
    local bake
    bake="$(mktemp)"
    dc build --print "$@" >"$bake"
    docker buildx bake -f "$bake" --allow=network.host "$@"
    rm -f "$bake"
  else
    dc build "$@"
  fi
}

ensure_docker
case "${1:-all}" in
  up) build viewer && dc up -d db viewer ;;
  scrape) build scraper && dc run --rm scraper ;;
  cluster) build clusterer && dc run --rm clusterer ;;
  all)
    build viewer scraper clusterer
    dc up -d db viewer
    dc run --rm scraper
    dc run --rm clusterer
    echo "Viewer: http://localhost:8080"
    ;;
  down) dc down ;;
  *) echo "Usage: $0 [all|up|scrape|cluster|down]" >&2; exit 1 ;;
esac
