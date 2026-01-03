#!/usr/bin/env sh
set -eu

host="${HOST:-0.0.0.0}"
port="${PORT:-8000}"
log_level="${LOG_LEVEL:-info}"

exec uv run uvicorn app.main:app \
  --host "${host}" \
  --port "${port}" \
  --log-level "${log_level}" \
  --log-config app/core/logging.yaml
