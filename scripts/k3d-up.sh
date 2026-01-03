#!/usr/bin/env bash
set -euo pipefail

cluster_name="${CLUSTER_NAME:-fastapi-template}"
namespace="${NAMESPACE:-dev}"

if ! command -v k3d >/dev/null 2>&1; then
  echo "k3d is required but not installed." >&2
  exit 1
fi

if ! k3d cluster list | grep -q "^${cluster_name}\\b"; then
  k3d cluster create "${cluster_name}" --agents 1 --servers 1 --port "8080:80@loadbalancer"
fi

kubectl create namespace "${namespace}" >/dev/null 2>&1 || true
