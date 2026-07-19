#!/usr/bin/env sh
set -eu

# Bootstrap upstream skills from installed packages into .claude/skills/_upstream/.
# Maps to mattwwarren/fastapi-template#14 (DRIFT-1).
#
# Flow:
#   1. uv run library-skills install --yes --copy --all
#      writes real files into .agents/skills/<name>/ (.agents/ is gitignored).
#   2. rsync each installed skill into .claude/skills/_upstream/<name>/.
#      The namespaced location prevents collisions with hand-authored skills
#      under .claude/skills/<name>/ (DRIFT-2 / #15 will add a guard hook).
#
# `library-skills --check --claude` will report vendored skills as
# `hand-authored` and exit non-zero. That is expected; the actual drift
# workflow is deferred to DRIFT-3.

# Clear the staging dir so re-runs always pick up the latest from .venv.
rm -rf .agents/skills

uv run library-skills install --yes --copy --all

mkdir -p .claude/skills/_upstream

installed=""
for d in .agents/skills/*/; do
  [ -d "$d" ] || continue
  name=$(basename "$d")
  rm -rf ".claude/skills/_upstream/$name"
  cp -a "${d%/}" ".claude/skills/_upstream/$name"
  installed="$installed $name"
done

if [ -z "$installed" ]; then
  echo "No upstream skills found in .agents/skills/. Did the install step succeed?" >&2
  exit 1
fi

echo "Vendored skills:$installed"
