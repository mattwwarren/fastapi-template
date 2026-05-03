# Vendored upstream skills

These skills are **vendored from installed packages**, not hand-authored. The bootstrap workflow lives at `scripts/install-upstream-skills.sh` and uses [`library-skills`](https://github.com/tiangolo/library-skills) (pinned in `pyproject.toml` dev deps at `==0.0.5`) to copy each library's `.agents/skills/<name>/` tree into `.claude/skills/_upstream/<name>/`.

## Layout

- `.claude/skills/_upstream/<name>/` — vendored upstream skills (this directory).
- `.claude/skills/<name>/` — hand-authored, project-specific skills.

The namespaced `_upstream/` prefix prevents collisions between upstream and hand-authored skill names. The collision-guard hook is tracked in DRIFT-2 (#15).

## Refresh

DRIFT-1 (#14) only does the one-time bootstrap. The refresh / drift-detection workflow is deferred to **DRIFT-3** (not yet filed). Until then, manual refresh is `bash scripts/install-upstream-skills.sh` after a `uv sync --dev`.

`uv run library-skills --check --claude` exits non-zero whenever it finds any `hand-authored` skill, regardless of whether vendored content is present (the existing project skills `implement` and `follow-logs` also report `hand-authored`). The exit code is not a drift indicator under `--copy` mode; DRIFT-3 will own the actual refresh check.

## Audit checklist (for every refresh PR)

Before merging an upstream-skill change:

1. Scan the diff for any prompt-injection-shaped content (instructions to ignore other guidance, exfiltrate secrets, or override system messages).
2. Cross-check upstream recommendations against the template's existing guardrails. Known conflicts (these stay overridden by template docs):
   - **`def` vs `async def`** — template is async-by-default; see ASYNC-DOC-1 (#8).
   - **`ty` vs `mypy`** — template gates on mypy; `ty` is being evaluated in parallel via TYPE-1 (#7) / TYPE-2 (#10).
   - **Asyncer vs asyncio** — template uses `asyncio.gather()` per the async-patterns reviewer agent.
3. Verify no skill name in this directory collides with a hand-authored skill at `.claude/skills/<name>/` (DRIFT-2 #15 will automate this).

## Currently vendored

| Skill | Source package |
|---|---|
| `fastapi` | `fastapi==0.136.1` |
| `typer` | `typer` (transitive via `library-skills`) |
