# DevSpace Command Map

Forbidden raw commands and their DevSpace/MCP alternatives. **Agents must use this lookup table instead of reaching for kubectl/k3d/docker/helm directly.**

## Substitution Table

### kubectl → DevSpace/MCP

| Forbidden Command | Alternative | Notes |
|---|---|---|
| `kubectl get pods` | `devspace run status` or MCP `devspace_status` | Shows pods, services, deployments |
| `kubectl get svc` | `devspace run status` or MCP `devspace_status` | Included in status output |
| `kubectl get deployments` | `devspace run status` or MCP `devspace_status` | Included in status output |
| `kubectl describe pod <name>` | MCP `devspace_kubectl_get` with args | Read-only describe is allowed but MCP is preferred |
| `kubectl logs <pod>` | `devspace logs <service>` or MCP `devspace_logs` | Use service name, not pod name |
| `kubectl exec -it <pod> -- bash` | `devspace enter <service>` or MCP `devspace_container_exec` | Use service name, not pod name |
| `kubectl exec <pod> -- <cmd>` | MCP `devspace_container_exec` | For one-off commands |
| `kubectl apply -f <file>` | `devspace deploy` | **Denied** — use DevSpace deployments |
| `kubectl create <resource>` | `devspace deploy` | **Denied** — use DevSpace deployments |
| `kubectl delete <resource>` | `devspace purge` | **Denied** — use DevSpace purge |
| `kubectl port-forward` | DevSpace dev mode auto-forwards | **Denied** — ports forwarded automatically |
| `kubectl patch/replace` | Modify Helm values in `devspace.yaml` | **Denied** — change config, redeploy |
| `kubectl run` | Add to `devspace.yaml` deployments | **Denied** — use DevSpace |
| `kubectl scale` | Modify replica count in `devspace.yaml` | **Denied** — change config, redeploy |
| `kubectl rollout restart` | `devspace restart` or MCP `devspace_restart` | **Denied** — use DevSpace |

### k3d → DevSpace

| Forbidden Command | Alternative | Notes |
|---|---|---|
| `k3d cluster create` | `devspace run cluster-up` | **Denied** — uses scripts/k3d-up.sh |
| `k3d cluster delete` | `devspace run k3d-down` | **Denied** — uses scripts/k3d-down.sh |
| `k3d image import` | Handled by DevSpace hooks | **Denied** — after:build hook auto-imports |
| `k3d node/registry` | Not needed | **Denied** — managed by cluster-up |

### docker → DevSpace

| Forbidden Command | Alternative | Notes |
|---|---|---|
| `docker build` | `devspace build` | **Denied** — DevSpace manages builds |
| `docker run` | `devspace deploy` + `devspace dev` | **Denied** — use k8s deployments |
| `docker exec` | `devspace enter` or MCP `devspace_container_exec` | **Denied** — use DevSpace |
| `docker stop/rm/rmi` | `devspace purge` | **Denied** — use DevSpace lifecycle |

### helm → DevSpace

| Forbidden Command | Alternative | Notes |
|---|---|---|
| `helm install/upgrade` | `devspace deploy` | **Denied** — DevSpace wraps Helm |
| `helm delete/uninstall` | `devspace purge` | **Denied** — DevSpace wraps Helm |

### Database Commands

| Task | Command | Notes |
|---|---|---|
| Run Alembic migration | `devspace run alembic-upgrade` or MCP `devspace_alembic_upgrade` | Executes inside container |
| Generate migration | `devspace run alembic-revision -- "message"` or MCP `devspace_alembic_revision` | Autogenerate only |
| psql shell | `devspace run db-shell` | Connects to postgres pod |

## Service Name Mapping

Agents must use **DevSpace service names**, not raw pod names:

| DevSpace Service | Pod Pattern | Label Selector |
|---|---|---|
| `api` (dev mode) | `devspace-app-*` | `app.kubernetes.io/name=devspace-app` |
| `postgres` | `postgres-0` | `app=postgres` |

## Common Agent Mistakes

### 1. Checking pod status with kubectl

**Wrong:**
```bash
kubectl get pods -n warren-enterprises-ltd
```

**Correct:**
```bash
devspace run status
# or use MCP: devspace_status
```

### 2. Tailing logs with kubectl

**Wrong:**
```bash
kubectl logs -f deployment/devspace-app -n warren-enterprises-ltd
```

**Correct:**
```bash
devspace logs -f
# or use MCP: devspace_logs with follow=true
```

### 3. Running a command inside the container

**Wrong:**
```bash
kubectl exec -it devspace-app-abc123 -n warren-enterprises-ltd -- bash
```

**Correct:**
```bash
devspace enter --container api
# or use MCP: devspace_container_exec
```

### 4. Creating the cluster manually

**Wrong:**
```bash
k3d cluster create fastapi-template --port "8000:80@loadbalancer"
```

**Correct:**
```bash
devspace run cluster-up
```

### 5. Running database migrations

**Wrong:**
```bash
kubectl exec -it devspace-app-abc123 -- alembic upgrade head
```

**Correct:**
```bash
devspace run alembic-upgrade
# or use MCP: devspace_alembic_upgrade
```

## Emergency Exceptions

Raw `kubectl` is acceptable **only** when ALL of these conditions are met:

1. You are in a `/debug-start` session
2. The user has explicitly approved raw command usage
3. DevSpace commands and MCP tools have been tried and failed
4. The command is read-only (get, describe, logs)

Even in emergencies, **mutating commands** (apply, delete, patch, scale) are never acceptable — always use DevSpace.
