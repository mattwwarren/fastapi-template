#!/usr/bin/env bash
set -euo pipefail

cluster_name="${CLUSTER_NAME:-{{ project_slug }}}"

if ! command -v k3d >/dev/null 2>&1; then
  echo "k3d is required but not installed." >&2
  exit 1
fi

k3d cluster delete "${cluster_name}"
