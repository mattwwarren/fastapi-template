#!/usr/bin/env bash
# templatize.sh - Convert runnable fastapi_template to copier template
#
# This script transforms the working Python project back into a Copier template
# by replacing hardcoded "fastapi_template" references with Jinja2 template
# variables ({{ project_slug }}).
#
# Usage:
#   ./scripts/templatize.sh [output_dir]
#
# Arguments:
#   output_dir - Target directory for templatized output (default: .templatized)
#
# The script:
# 1. Copies the project excluding dev artifacts (.git, __pycache__, .venv, etc.)
# 2. Renames fastapi_template/ directory to {{ project_slug }}/
# 3. Replaces "fastapi_template" with "{{ project_slug }}" in Python files
# 4. Updates pyproject.toml, alembic.ini, alembic/env.py
# 5. Preserves existing Jinja2 templated files (QUICKSTART.md, dotenv.example)

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory (resolve symlinks)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Default output directory
OUTPUT_DIR="${1:-.templatized}"

# Convert to absolute path if relative
if [[ ! "${OUTPUT_DIR}" = /* ]]; then
    OUTPUT_DIR="${PROJECT_ROOT}/${OUTPUT_DIR}"
fi

echo -e "${GREEN}=== Templatization Script ===${NC}"
echo "Source: ${PROJECT_ROOT}"
echo "Output: ${OUTPUT_DIR}"
echo ""

# Clean output directory if it exists
if [[ -d "${OUTPUT_DIR}" ]]; then
    echo -e "${YELLOW}Removing existing output directory...${NC}"
    rm -rf "${OUTPUT_DIR}"
fi

# Create output directory
mkdir -p "${OUTPUT_DIR}"

# Step 1: Copy project excluding dev artifacts
echo -e "${GREEN}[1/5] Copying project (excluding dev artifacts)...${NC}"

# Files and directories to exclude
EXCLUDE_PATTERNS=(
    ".git"
    ".venv"
    "__pycache__"
    "*.pyc"
    "*.pyo"
    "*.pyd"
    ".pytest_cache"
    ".mypy_cache"
    ".ruff_cache"
    ".coverage"
    "htmlcov"
    ".env"
    ".env.*"
    "*.egg-info"
    "build"
    "dist"
    ".build"
    ".dist"
    ".DS_Store"
    ".devspace"
    "uploads"
    "docs/_build"
    ".templatized"
    "uv.lock"
    # Template infrastructure files (not for generated projects)
    ".github/workflows/publish-template.yml"
    "scripts/templatize.sh"
)

# Build rsync exclude arguments
RSYNC_EXCLUDES=()
for pattern in "${EXCLUDE_PATTERNS[@]}"; do
    RSYNC_EXCLUDES+=("--exclude=${pattern}")
done

# Copy using rsync (preserves symlinks, permissions)
rsync -a "${RSYNC_EXCLUDES[@]}" "${PROJECT_ROOT}/" "${OUTPUT_DIR}/"

echo "  Copied $(find "${OUTPUT_DIR}" -type f | wc -l) files"

# Template variable - the target directory name with Jinja2 syntax
# Use hex codes in sed pattern to avoid brace interpretation issues
TEMPLATE_VAR='{{ project_slug }}'
SED_REPLACEMENT='\x7B\x7B project_slug \x7D\x7D'

# Step 2: Replace fastapi_template references in Python files FIRST (before rename)
# This avoids dealing with curly braces in paths
echo -e "${GREEN}[2/5] Replacing references in Python files...${NC}"

# Find all .py files in fastapi_template directory
if [[ ! -d "${OUTPUT_DIR}/fastapi_template" ]]; then
    echo -e "${RED}ERROR: fastapi_template/ directory not found${NC}"
    exit 1
fi

PY_COUNT=0
while IFS= read -r -d '' file; do
    if grep -q "fastapi_template" "$file" 2>/dev/null; then
        # Replace fastapi_template with {{ project_slug }}
        sed -i "s/fastapi_template/${SED_REPLACEMENT}/g" "$file"
        ((PY_COUNT++)) || true  # Prevent exit on first increment (0 returns false)
    fi
done < <(find "${OUTPUT_DIR}/fastapi_template" -name "*.py" -print0 2>/dev/null)

echo "  Updated ${PY_COUNT} Python files in package"

# Step 3: Rename fastapi_template/ to {{ project_slug }}/
echo -e "${GREEN}[3/5] Renaming package directory...${NC}"

mv "${OUTPUT_DIR}/fastapi_template" "${OUTPUT_DIR}/${TEMPLATE_VAR}"
echo "  Renamed: fastapi_template/ -> ${TEMPLATE_VAR}/"

# Step 4: Update configuration files at project root
echo -e "${GREEN}[4/5] Updating configuration files...${NC}"

# pyproject.toml - replace package references
if [[ -f "${OUTPUT_DIR}/pyproject.toml" ]]; then
    sed -i "s/fastapi_template/${SED_REPLACEMENT}/g" "${OUTPUT_DIR}/pyproject.toml"
    echo "  Updated: pyproject.toml"
fi

# alembic.ini - no changes needed (doesn't reference fastapi_template)
echo "  Checked: alembic.ini (no changes needed)"

# alembic/env.py - replace import references
if [[ -f "${OUTPUT_DIR}/alembic/env.py" ]]; then
    sed -i "s/fastapi_template/${SED_REPLACEMENT}/g" "${OUTPUT_DIR}/alembic/env.py"
    echo "  Updated: alembic/env.py"
fi

# tests/ directory - replace references in test files
if [[ -d "${OUTPUT_DIR}/tests" ]]; then
    TEST_COUNT=0
    while IFS= read -r -d '' file; do
        if grep -q "fastapi_template" "$file" 2>/dev/null; then
            sed -i "s/fastapi_template/${SED_REPLACEMENT}/g" "$file"
            ((TEST_COUNT++)) || true
        fi
    done < <(find "${OUTPUT_DIR}/tests" -name "*.py" -print0 2>/dev/null)
    echo "  Updated ${TEST_COUNT} test files"
fi

# _tasks.py - if it references the package
if [[ -f "${OUTPUT_DIR}/_tasks.py" ]]; then
    if grep -q "fastapi_template" "${OUTPUT_DIR}/_tasks.py" 2>/dev/null; then
        sed -i "s/fastapi_template/${SED_REPLACEMENT}/g" "${OUTPUT_DIR}/_tasks.py"
        echo "  Updated: _tasks.py"
    fi
fi

# Step 5: Verify Jinja2 templated files are preserved
echo -e "${GREEN}[5/5] Verifying Jinja2 templated files...${NC}"

JINJA_FILES=(
    "QUICKSTART.md"
    "dotenv.example"
    "copier.yaml"
)

for file in "${JINJA_FILES[@]}"; do
    if [[ -f "${OUTPUT_DIR}/${file}" ]]; then
        # Check if file contains Jinja2 syntax
        if grep -qE '\{\{|\{%' "${OUTPUT_DIR}/${file}" 2>/dev/null; then
            echo "  Preserved: ${file} (contains Jinja2 syntax)"
        else
            echo -e "${YELLOW}  Warning: ${file} may be missing Jinja2 syntax${NC}"
        fi
    else
        echo -e "${YELLOW}  Warning: ${file} not found${NC}"
    fi
done

# Summary
echo ""
echo -e "${GREEN}=== Templatization Complete ===${NC}"
echo ""
echo "Output directory: ${OUTPUT_DIR}"
echo ""
echo "Directory structure:"
ls -la "${OUTPUT_DIR}/" | head -20

echo ""
echo "To test the template:"
echo "  copier copy ${OUTPUT_DIR} /tmp/test-project \\"
echo "    --data project_name=\"My Project\" \\"
echo "    --data project_slug=\"my_project\" \\"
echo "    --defaults --trust"
echo ""
echo "To verify the generated project:"
echo "  cd /tmp/test-project"
echo "  uv sync"
echo "  uv run ruff check ."
echo "  uv run mypy ."
echo "  uv run pytest"
