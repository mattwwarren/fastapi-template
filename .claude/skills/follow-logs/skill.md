---
name: follow-logs
description: Follow service logs using DevSpace or MCP
argument-hint: "[service-name]"
---

# Follow Service Logs

Stream logs from services running in the DevSpace development cluster.

## Usage

```bash
/follow-logs          # Follow backend (api) logs
/follow-logs api      # Follow backend explicitly
/follow-logs postgres # Follow postgres logs
```

## How to Follow Logs

### Option 1: DevSpace CLI (preferred for interactive streaming)

```bash
# Follow backend logs
devspace logs -f

# Follow with last N lines
devspace logs -f --tail 100
```

### Option 2: MCP Tool (preferred for agents)

Use the `devspace_logs` MCP tool:
- `service`: service name (e.g., `api`)
- `follow`: `true` for streaming
- `tail`: number of recent lines

### Option 3: devspace run status (quick check)

```bash
# See pod status first, then decide what to tail
devspace run status
```

## Debugging Production Issues

When investigating problems, use this workflow:

1. **Check status**: `devspace run status` or MCP `devspace_status`
2. **Follow logs**: `devspace logs -f` or MCP `devspace_logs`
3. **Health check**: `devspace run health` or MCP `devspace_health_check`
4. **Enter container**: `devspace enter --container api` or MCP `devspace_container_exec`
5. **Full diagnostics**: `devspace run troubleshoot`

## Structured Logs

This backend uses structured JSON logging. Look for:

```json
{
  "timestamp": "2024-01-04T19:30:00Z",
  "level": "error",
  "event": "database_connection_failed",
  "error": "Connection timeout",
  "retry_count": 3
}
```

**Tip:** Use `jq` to filter JSON logs: `devspace logs | jq 'select(.level == "error")'`

## Important

Do NOT use raw `kubectl logs` — it is blocked by deny rules. Always use DevSpace commands or MCP tools.
