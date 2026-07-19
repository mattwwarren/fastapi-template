---
description: "Ship the current branch as a PR (fastapi-template project ship-it)"
argument-hint: "[--base <branch>] [--title <value>]"
allowed-tools: ["Bash", "Read"]
---

# Ship It (fastapi-template)

Project-level ship-it for `fastapi-template`. Runs after `/prep-pr` finishes its
self-review and quality gates. Covers push and PR creation only — this repo has
auto-merge disabled, so merging is handled by the operator/orchestrator after
the `validate-template` workflow is green. Do not attempt `gh pr merge --auto`.

**Arguments:** "$ARGUMENTS"

Quality gates (`uv run ruff check`, `uv run mypy`, `uv run pytest`) are handled
by `/prep-pr` — do not re-run them here.

## Step 1: Parse arguments

Base defaults to `main`; override with `--base <branch>`. Extract `--title <value>`
into `EXPLICIT_TITLE` if provided.

## Step 2: Push the branch

```bash
BRANCH=$(git branch --show-current)
git push -u origin "$BRANCH"
```

If push fails (e.g. diverged), BLOCK — never force-push without explicit user
approval.

## Step 3: Create the PR

Draft the title from the branch's commits (or use `EXPLICIT_TITLE`). Body must:

- Reference the ticket: `Closes #<ticket>` (branch names are `dev/<ticket>`)
- Summarize the change set and call out anything a reviewer would ask about
  (holdbacks added, acceptance-bar notes, known pre-existing failures with
  their tracking ticket)
- End with the Claude Code attribution line

```bash
gh pr create --base "$BASE" --head "$BRANCH" --title "$TITLE" --body "$BODY"
```

## Step 4: Report

Print the PR URL and the CI status command (`gh pr checks <num>`). Do NOT merge
and do NOT enable auto-merge — the merge decision belongs to the
operator/orchestrator once `validate-template` is green.
