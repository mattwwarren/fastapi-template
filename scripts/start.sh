#!/usr/bin/env sh
set -eu

host="${HOST:-0.0.0.0}"
port="${PORT:-8000}"

exec uv run uvicorn app.main:app \
  --host "${host}" \
  --port "${port}" \
  --log-config app/core/logging.yaml
