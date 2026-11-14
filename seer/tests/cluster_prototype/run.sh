#!/usr/bin/env bash
# Shortcut for the Makefile. Usage: ./run.sh [all|up|scrape|cluster|down|...]; `make help` lists every target.
set -euo pipefail
exec make -C "$(dirname "$0")" "${1:-all}"
