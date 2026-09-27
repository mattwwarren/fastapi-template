# Type Checker Comparison: `ty` vs `mypy`

**Run date:** 2026-09-27
**`ty` pin:** `ty@0.0.84` (invoked via `uvx`, matching CI's `ty-check` job)
**`ty` invocation:** `uvx ty@0.0.84 check fastapi_template/ --output-format concise`
**`mypy` invocation:** `uv run mypy fastapi_template` (config: `pyproject.toml` `[tool.mypy]`, `mypy_path = "stubs"`, plus `[[tool.mypy.overrides]]` for `azure.*`/`google.*`/`socketio.*`)

**Raw results:**
- `ty`: 64 diagnostics (62 error, 2 warning) across 25 files
- `mypy`: `Success: no issues found in 109 source files` — 0 errors

No `[tool.ty]` config section exists in `pyproject.toml`. `ty` does not honor `mypy_path` or `[[tool.mypy.overrides]]`, which is the root cause of most of the divergence below.

Every `ty` finding was cross-checked against the file it flags to determine whether the line already carries a `mypy`-targeted `# type: ignore[...]` comment. That check is the split driver between the buckets below.

## Bucket (a): Real bugs mypy missed

2 root causes, 5 diagnostics. Not fixed in this PR — tracked for a follow-up ticket.

1. **`fastapi_template/core/permissions.py:217-219`** (3 diagnostics) — `require_role()` is declared `-> object` (line 125) but actually returns the callable `_check_role`. `Depends(require_role(...))` fails against FastAPI's real `Depends(dependency: Callable[..., Any] | None = ...)` signature because `object` doesn't structurally satisfy `Callable[..., Any]`. Tightening the return annotation would be a legitimate no-ignore-needed fix, but is out of scope here.
   - Why `mypy` doesn't flag this is an open question — not fully isolated at triage time. This is a settled footnote for this ticket; a follow-up ticket may isolate the mechanism later. The triage recommendation below does not depend on the answer.
2. **`fastapi_template/tests/fixtures/settings.py:102,106`** (2 diagnostics) — a hand-built `list[InitErrorDetails]` dict literal passed to `ValidationError.from_exception_data` includes a `"msg"` key that isn't part of pydantic-core's real `InitErrorDetails` TypedDict (`invalid-key: Unknown key "msg"`). Test-only, low severity, genuine drift from the real contract that mypy's default mode didn't catch.

## Bucket (b): `ty` false positives / config-portability gaps

52 diagnostics. Every one lands on a line that already carries a `mypy`-targeted `# type: ignore[...]` (or is a documented, accepted static-analysis limitation) — `ty` is independently re-discovering already-accepted decisions, not surfacing new risk. Three representative root causes:

1. **Local stub override not respected (`mypy_path`).** `stubs/slowapi/__init__.pyi:29` types `storage_options` as `Mapping[str, object] | None` for `mypy`. `ty` doesn't consume `mypy_path`, so it resolves against upstream `slowapi`'s real, narrower `str`-only annotation and flags the `dict[str, int]` call sites in `fastapi_template/main.py:273` and `tests/unit/test_main_rate_limiting.py:96,142`.
2. **`[[tool.mypy.overrides]]` `ignore_missing_imports` not respected.** `fastapi_template/core/storage_providers.py:96,99,104,106,107` import `azure.*`/`google.*`, suppressed for `mypy` via override blocks. `ty` has no equivalent config and reports `unresolved-import` on each.
3. **SQLModel metaclass `model_config` gap.** `fastapi_template/models/{activity_log,document,membership,organization,shared,user}.py` (7 diagnostics) all do `model_config: ClassVar[ConfigDict] = ConfigDict(...)  # type: ignore[assignment]`. This is a known upstream SQLModel/`ty` gap — `sqlmodel/main.py:648` itself carries a `# ty: ignore[invalid-key]`.

Other pre-suppressed clusters in this bucket: `core/storage.py:192-274` (13, lazy-init `Settings | None` pattern), `api/organizations.py:79` / `users.py:95` (fastapi-pagination variance), `core/activity_logging.py:306,324`, `main.py:278` / `tests/unit/test_main_rate_limiting.py:150` (`add_exception_handler`), `tests/fixtures/settings.py:116`, `tests/conftest.py` (6), `tests/integration/test_race_conditions.py` (4), `tests/integration/test_migrations.py:35`, `tests/unit/test_storage_optional_deps.py:54`, and two narrow static-analysis limitations without literal pre-existing ignores: `core/tenants.py:163` (hasattr narrowing) and `db/retry.py:116` / `core/storage_providers.py:228` (PEP 612 ParamSpec edge case, 2 diagnostics each).

## Bucket (c): Style differences / stricter-by-default

7 diagnostics, no pre-existing suppression, low severity:

- `fastapi_template/cache/decorator.py:51,108,121` — accesses `func.__name__` on a `Callable[..., object]`-typed parameter; every real call site passes a `def`/`async def`, so this never fails at runtime.
- `fastapi_template/core/auth.py:533` and `tests/integration/test_realtime_e2e.py:341` — `warning[possibly-missing-submodule]` on `jwt.algorithms` / `socketio.exceptions`.
- `tests/unit/test_auth_unit.py:504,512` — deliberately passes the wrong type to exercise an error-handling path.

## Recommendation: keep parallel + non-blocking

1. 81% of `ty`'s findings (52/64) are not new information — they're known, already-accepted `mypy` suppressions resurfacing because `ty` (pinned pre-1.0 `ty@0.0.84`, no `[tool.ty]` config) doesn't honor `mypy`'s override mechanisms. Gating CI on `ty` today means re-litigating ~52 accepted decisions or writing a parallel suppression syntax for no new safety.
2. `ty` did surface 2 small, genuinely real, previously-unknown gaps (bucket a) — proof of some incremental value, but not yet "block the merge" maturity.
3. `ty` is explicitly version-pinned as a fast-moving pre-1.0 tool; worth revisiting after it reaches stable/1.0, or after `mypy_path`/overrides get ported to a `[tool.ty]` section.
4. "Scope-and-block" per directory isn't viable yet — every directory with `ty`-clean files still has at least one still-suppressed pattern elsewhere in it.
5. "Replace `mypy` entirely" is premature — `mypy` is the enforced zero-error gate today; `ty` currently produces more noise than signal without ported overrides.

This satisfies the ticket's three-way choice (parallel+non-blocking / scope-and-block / replace) with **keep parallel + non-blocking**. Current CI config (`ci.yml`'s `ty-check` job, `continue-on-error: true`) already implements this recommendation — no CI or config change is needed as part of this ticket.

## Follow-up

A follow-up ticket, [#82](https://github.com/mattwwarren/fastapi-template/issues/82), will track:
1. Fixing the 2 bucket-(a) findings (`permissions.py` return type, `settings.py` fixture `InitErrorDetails` literal).
2. Optionally porting `mypy_path`/overrides to a `[tool.ty]` section to cut bucket-(b) noise.
3. A re-triage trigger: `ty` reaching stable/1.0, or a fixed number of months elapsed.
