#!/usr/bin/env bash
# Diagnostic script for fastapi-template DevSpace environment.
# Checks Docker, k3d, kubectl, namespace, pods, services, and ports.
# Outputs pass/fail per step with actionable fix suggestions.

set -euo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-fastapi-template}"
NAMESPACE="${NAMESPACE:-warren-enterprises-ltd}"
APP_PORT="${APP_PORT:-8000}"

pass=0
fail=0

check() {
  local label="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    echo "  [PASS] $label"
    ((pass++))
  else
    echo "  [FAIL] $label"
    ((fail++))
    return 1
  fi
  return 0
}

echo "=== DevSpace Troubleshoot ==="
echo ""

# 1. Docker
echo "-- Docker --"
if check "Docker daemon running" docker info; then
  :
else
  echo "    Fix: Start Docker Desktop or run 'systemctl start docker'"
fi

# 2. k3d
echo ""
echo "-- k3d --"
if check "k3d CLI installed" command -v k3d; then
  if k3d cluster list 2>/dev/null | grep -q "^${CLUSTER_NAME} "; then
    echo "  [PASS] Cluster '${CLUSTER_NAME}' exists"
    ((pass++))

    # Check cluster is running (not stopped)
    if k3d cluster list 2>/dev/null | grep "^${CLUSTER_NAME} " | grep -q "1/1"; then
      echo "  [PASS] Cluster '${CLUSTER_NAME}' is running"
      ((pass++))
    else
      echo "  [FAIL] Cluster '${CLUSTER_NAME}' exists but not fully running"
      ((fail++))
      echo "    Fix: devspace run cluster-up"
    fi
  else
    echo "  [FAIL] Cluster '${CLUSTER_NAME}' not found"
    ((fail++))
    echo "    Fix: devspace run cluster-up"
  fi
else
  echo "    Fix: Install k3d — see https://k3d.io"
fi

# 3. kubectl context
echo ""
echo "-- kubectl --"
if check "kubectl CLI installed" command -v kubectl; then
  current_context=$(kubectl config current-context 2>/dev/null || echo "none")
  expected_context="k3d-${CLUSTER_NAME}"
  if [ "$current_context" = "$expected_context" ]; then
    echo "  [PASS] kubectl context is '${expected_context}'"
    ((pass++))
  else
    echo "  [FAIL] kubectl context is '${current_context}', expected '${expected_context}'"
    ((fail++))
    echo "    Fix: kubectl config use-context ${expected_context}"
  fi
else
  echo "    Fix: Install kubectl"
fi

# 4. Namespace
echo ""
echo "-- Namespace --"
if kubectl get namespace "${NAMESPACE}" >/dev/null 2>&1; then
  echo "  [PASS] Namespace '${NAMESPACE}' exists"
  ((pass++))
else
  echo "  [FAIL] Namespace '${NAMESPACE}' not found"
  ((fail++))
  echo "    Fix: kubectl create namespace ${NAMESPACE}"
fi

# 5. Pods
echo ""
echo "-- Pods (${NAMESPACE}) --"
pod_output=$(kubectl get pods -n "${NAMESPACE}" --no-headers 2>/dev/null || echo "")
if [ -z "$pod_output" ]; then
  echo "  [FAIL] No pods found in namespace '${NAMESPACE}'"
  ((fail++))
  echo "    Fix: devspace deploy"
else
  echo "$pod_output" | while IFS= read -r line; do
    pod_name=$(echo "$line" | awk '{print $1}')
    pod_status=$(echo "$line" | awk '{print $3}')
    ready=$(echo "$line" | awk '{print $2}')
    if [ "$pod_status" = "Running" ]; then
      echo "  [PASS] ${pod_name} — ${pod_status} (${ready})"
    else
      echo "  [FAIL] ${pod_name} — ${pod_status} (${ready})"
    fi
  done
fi

# 6. Services
echo ""
echo "-- Services (${NAMESPACE}) --"
svc_output=$(kubectl get svc -n "${NAMESPACE}" --no-headers 2>/dev/null || echo "")
if [ -z "$svc_output" ]; then
  echo "  [FAIL] No services found"
  ((fail++))
  echo "    Fix: devspace deploy"
else
  echo "$svc_output" | while IFS= read -r line; do
    svc_name=$(echo "$line" | awk '{print $1}')
    svc_type=$(echo "$line" | awk '{print $2}')
    svc_ports=$(echo "$line" | awk '{print $5}')
    echo "  [INFO] ${svc_name} (${svc_type}) — ports: ${svc_ports}"
  done
fi

# 7. Port availability
echo ""
echo "-- Port Availability --"
if command -v ss >/dev/null 2>&1; then
  port_check_cmd="ss -tlnp"
elif command -v lsof >/dev/null 2>&1; then
  port_check_cmd="lsof -iTCP -sTCP:LISTEN -P"
else
  port_check_cmd=""
fi

if [ -n "$port_check_cmd" ]; then
  if $port_check_cmd 2>/dev/null | grep -q ":${APP_PORT} "; then
    echo "  [INFO] Port ${APP_PORT} is in use (expected if dev mode is active)"
  else
    echo "  [INFO] Port ${APP_PORT} is available"
  fi
else
  echo "  [INFO] Cannot check ports (neither ss nor lsof available)"
fi

# Summary
echo ""
echo "=== Summary ==="
echo "  Passed: ${pass}"
echo "  Failed: ${fail}"

if [ "$fail" -gt 0 ]; then
  echo ""
  echo "Run 'devspace run cluster-up' to set up the cluster, then 'devspace deploy'."
  exit 1
else
  echo ""
  echo "All checks passed. Environment looks healthy."
  exit 0
fi
