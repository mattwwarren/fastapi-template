#!/usr/bin/env bash

# FastAPI Template Test Instance Manager
# Manage persistent test instance for template verification and development

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

TEMPLATE_DIR="$HOME/workspace/meta-work/fastapi-template"
TEST_INSTANCE_DIR="$HOME/workspace/meta-work/fastapi-template-test-instance"
PROJECT_NAME="FastAPI Template Test"
PROJECT_SLUG="fastapi_template_test"
DESCRIPTION="Test instance for template verification and development"
PORT=8100

# ============================================================================
# Color Output Helpers
# ============================================================================

readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m'  # No Color

_green() {
	echo -e "${GREEN}$*${NC}"
}

_red() {
	echo -e "${RED}$*${NC}"
}

_yellow() {
	echo -e "${YELLOW}$*${NC}"
}

_blue() {
	echo -e "${BLUE}$*${NC}"
}

# ============================================================================
# Utility Functions
# ============================================================================

_info() {
	echo -e "${BLUE}ℹ${NC} $*"
}

_success() {
	echo -e "${GREEN}✓${NC} $*"
}

_error() {
	echo -e "${RED}✗${NC} $*" >&2
}

_warn() {
	echo -e "${YELLOW}⚠${NC} $*"
}

_ask_confirmation() {
	local prompt="$1"
	local response
	read -p "$(echo -e "${YELLOW}?${NC} $prompt (y/n) ")" -n 1 -r response
	echo
	[[ $response =~ ^[Yy]$ ]]
}

# ============================================================================
# Generate - Create fresh test instance
# ============================================================================

_generate() {
	_info "Starting test instance generation..."

	# Check if instance exists
	if [[ -d "$TEST_INSTANCE_DIR" ]]; then
		_warn "Test instance already exists at: $TEST_INSTANCE_DIR"
		if _ask_confirmation "Remove and regenerate?"; then
			_info "Removing existing instance..."
			rm -rf "$TEST_INSTANCE_DIR"
		else
			_error "Generation cancelled"
			return 1
		fi
	fi

	# Create directory
	_info "Creating instance directory..."
	mkdir -p "$TEST_INSTANCE_DIR"

	# Generate from template using copier
	_info "Generating from template using copier..."
	if ! copier copy \
		"$TEMPLATE_DIR" \
		"$TEST_INSTANCE_DIR" \
		--data "project_name=$PROJECT_NAME" \
		--data "project_slug=$PROJECT_SLUG" \
		--data "description=$DESCRIPTION" \
		--data "port=$PORT" \
		--trust; then
		_error "Copier generation failed"
		rm -rf "$TEST_INSTANCE_DIR"
		return 1
	fi

	# Initialize git repository (required for copier update)
	_info "Initializing git repository..."
	cd "$TEST_INSTANCE_DIR"
	git init
	git config user.email "template-test@local" || true
	git config user.name "Template Test" || true

	# Create .copier-answers.yml for future updates
	_info "Creating copier answers file for future updates..."
	local template_commit
	template_commit=$(cd "$TEMPLATE_DIR" && git rev-parse HEAD || echo "unknown")
	cat >.copier-answers.yml <<EOF
_src_path: $TEMPLATE_DIR
_commit: $template_commit
project_name: $PROJECT_NAME
project_slug: $PROJECT_SLUG
description: $DESCRIPTION
port: $PORT
EOF

	# Add all files including .copier-answers.yml
	git add .
	git commit -m "Initial generation from fastapi-template" || true

	# Install dependencies
	_info "Installing dependencies with uv..."
	if ! uv sync; then
		_error "Dependency installation failed"
		return 1
	fi

	_success "Test instance generated successfully"
	_info "Location: $TEST_INSTANCE_DIR"
	_info "Next steps:"
	echo "  - Verify quality: $0 verify"
	echo "  - Update from template: $0 sync"
	echo "  - Enter shell: $0 shell"
}

# ============================================================================
# Verify - Run quality checks (ruff, mypy, pytest)
# ============================================================================

_verify() {
	_info "Running verification checks..."

	if [[ ! -d "$TEST_INSTANCE_DIR" ]]; then
		_error "Test instance not found at: $TEST_INSTANCE_DIR"
		_info "Generate first: $0 generate"
		return 1
	fi

	cd "$TEST_INSTANCE_DIR"

	local failed=0

	# Ruff check
	_info "Running ruff check..."
	if ! uv run ruff check .; then
		_error "Ruff check failed"
		failed=1
	else
		_success "Ruff check passed (0 violations)"
	fi

	# MyPy type checking
	_info "Running mypy type checking..."
	if ! uv run mypy "$PROJECT_SLUG"; then
		_error "MyPy type checking failed"
		failed=1
	else
		_success "MyPy type checking passed (0 errors)"
	fi

	# Pytest
	_info "Running pytest..."
	if ! uv run pytest; then
		_error "Pytest failed"
		_warn "Note: Ensure Docker is running for database tests"
		failed=1
	else
		_success "Pytest passed (100%)"
	fi

	if [[ $failed -eq 0 ]]; then
		_success "All verification checks passed!"
		return 0
	else
		_error "Some checks failed"
		return 1
	fi
}

# ============================================================================
# Sync - Update from template changes using copier update
# ============================================================================

_sync() {
	_info "Syncing test instance with template changes..."

	if [[ ! -d "$TEST_INSTANCE_DIR" ]]; then
		_error "Test instance not found at: $TEST_INSTANCE_DIR"
		_info "Generate first: $0 generate"
		return 1
	fi

	cd "$TEST_INSTANCE_DIR"

	# Check for uncommitted changes
	if ! git diff-index --quiet HEAD --; then
		_warn "Test instance has uncommitted changes"
		if ! _ask_confirmation "Proceed with sync (may cause merge conflicts)?"; then
			_error "Sync cancelled"
			return 1
		fi
	fi

	# Run copier update
	_info "Running copier update..."
	if copier update --trust; then
		_success "Test instance synced successfully"
		_info "Next steps:"
		echo "  - Verify changes: $0 verify"
		echo "  - Review git status: git status"
		echo "  - Review git diff: git diff"
		return 0
	else
		_warn "Copier update encountered issues"
		_info "Check git status for conflicts: git status"
		_info "Resolve conflicts and run: git add . && git commit -m 'Merge template changes'"
		_info "Then verify: $0 verify"
		return 1
	fi
}

# ============================================================================
# Reverse Sync - Sync fixes from instance back to template
# ============================================================================

_map_instance_path_to_template() {
	local instance_path="$1"
	# Replace project slug with Jinja2 variable
	echo "$instance_path" | sed "s|${PROJECT_SLUG}|{{ project_slug }}|g"
}

_reverse_sync() {
	_info "Starting reverse sync (instance → template)..."

	if [[ ! -d "$TEST_INSTANCE_DIR" ]]; then
		_error "Test instance not found at: $TEST_INSTANCE_DIR"
		_info "Generate first: $0 generate"
		return 1
	fi

	if [[ ! -d "$TEMPLATE_DIR/.git" ]]; then
		_error "Template directory is not a git repository"
		return 1
	fi

	cd "$TEMPLATE_DIR"

	# Check template is clean
	if ! git diff-index --quiet HEAD --; then
		_error "Template has uncommitted changes"
		_info "Either commit them or stash: git stash"
		return 1
	fi

	cd "$TEST_INSTANCE_DIR"

	# Get the base commit - find the commit that generated this instance
	# This is usually the first commit or a commit message containing "generation"
	local base_commit
	if [[ ! -f ".copier-answers.yml" ]]; then
		_error "No .copier-answers.yml found - not a copier-generated instance"
		return 1
	fi

	# Look for the "generation" commit (where copier created the instance)
	base_commit=$(git log --oneline --all | grep -i "generation\|initial" | tail -1 | awk '{print $1}')
	if [[ -z "$base_commit" ]]; then
		# Fall back to the first commit if we can't find a generation commit
		base_commit=$(git rev-list --max-parents=0 HEAD)
	fi

	# Get list of changed files since instance generation (uncommitted + committed)
	local changed_files=()
	while IFS= read -r file; do
		# Skip these files - they're regenerated or instance-specific
		case "$file" in
		uv.lock | uploads/* | .mypy_cache/* | .pytest_cache/* | .ruff_cache/*)
			continue
			;;
		esac
		changed_files+=("$file")
	done < <({
		git diff --name-only
		git diff --name-only "$base_commit..HEAD"
	} | sort -u)

	if [[ ${#changed_files[@]} -eq 0 ]]; then
		_info "No changes to sync"
		return 0
	fi

	_success "Found ${#changed_files[@]} file(s) to sync"
	echo ""

	# Determine if auto mode (--auto flag)
	local auto_mode=0
	if [[ "${2:-}" == "--auto" ]]; then
		auto_mode=1
	fi

	# Interactive review of each file
	local files_to_sync=()
	local file_count=0
	for file in "${changed_files[@]}"; do
		((file_count++))
		local template_path
		template_path=$(_map_instance_path_to_template "$file")

		if [[ $auto_mode -eq 0 ]]; then
			echo ""
			_blue "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
			_blue "File $file_count/${#changed_files[@]}: $file"
			_blue "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
			echo ""
			echo "Template path: $template_path"
			echo ""
			echo "Changes:"
			git diff --color=always "$file" | head -30
			if [[ $(git diff "$file" | wc -l) -gt 30 ]]; then
				_yellow "(... truncated, showing first 30 lines)"
			fi
			echo ""
		fi

		if [[ $auto_mode -eq 1 ]]; then
			echo ""
			_info "File $file_count/${#changed_files[@]}: $file"
			_success "Syncing in auto mode"
			files_to_sync+=("$file")
		else
			read -p "$(echo -e "${YELLOW}?${NC} Sync this file? (y/n/q) ")" -n 1 -r response
			echo ""
			case $response in
			[Yy])
				files_to_sync+=("$file")
				;;
			[Qq])
				_info "Sync cancelled"
				return 0
				;;
			[Nn])
				_warn "Skipping this file"
				;;
			esac
		fi
	done

	# Apply changes to template
	if [[ ${#files_to_sync[@]} -eq 0 ]]; then
		_info "No files selected for syncing"
		return 0
	fi

	echo ""
	_info "Applying changes to template..."

	local temp_dir
	temp_dir=$(mktemp -d)
	trap "rm -rf $temp_dir" EXIT

	for file in "${files_to_sync[@]}"; do
		local template_path
		template_path=$(_map_instance_path_to_template "$file")

		# Generate patch with transformed paths
		# Use git diff between base commit and HEAD to capture all changes (committed + uncommitted)
		local patch_file="$temp_dir/$(echo "$file" | tr '/' '_').patch"

		# Try committed changes first (since instance generation)
		if git diff "$base_commit..HEAD" "$file" | grep -q .; then
			git diff "$base_commit..HEAD" "$file" > "$patch_file"
		else
			# Fall back to uncommitted changes if no committed changes
			git diff "$file" > "$patch_file"
		fi

		# Transform paths in patch
		sed -i "s|a/${PROJECT_SLUG}/|a/{{ project_slug }}/|g" "$patch_file"
		sed -i "s|b/${PROJECT_SLUG}/|b/{{ project_slug }}/|g" "$patch_file"

		# Apply to template
		cd "$TEMPLATE_DIR"
		if git apply "$patch_file"; then
			_success "Applied: $template_path"
		else
			_error "Failed to apply patch for: $template_path"
			_info "Patch file available at: $patch_file"
			_error "Sync failed - reverting template changes"
			git reset --hard HEAD
			return 1
		fi
	done

	echo ""
	_success "Changes applied to template (${#files_to_sync[@]} file(s))"

	# Roundtrip verification
	echo ""
	_info "Running roundtrip verification..."
	_info "This tests that changes survive: Template → Instance transformation"

	cd "$TEST_INSTANCE_DIR"

	# Create temporary commit for stash
	local before_stash_sha
	before_stash_sha=$(git rev-parse HEAD)

	# Stash any uncommitted changes
	git stash push -m "reverse-sync backup" --quiet || true

	# Run copier update
	_info "Updating test instance from modified template..."
	if ! copier update --trust 2>&1 | grep -v "^Copying" | grep -v "^Patching"; then
		_error "Roundtrip failed - copier update encountered issues"
		_info "Rolling back template changes..."
		cd "$TEMPLATE_DIR"
		git reset --hard HEAD
		_error "Sync failed"
		return 1
	fi

	# Check for unexpected changes (roundtrip should be idempotent)
	if ! git diff-index --quiet HEAD --; then
		_error "Roundtrip failed - template changes produced unexpected diffs"
		echo ""
		_warn "Unexpected changes after copier update:"
		git diff --stat
		_info "Rolling back template changes..."
		cd "$TEMPLATE_DIR"
		git reset --hard HEAD
		_error "Sync failed"
		return 1
	fi

	_success "Roundtrip verification passed"

	# Restore stashed changes if any
	git stash pop --quiet 2>/dev/null || true

	# Run quality checks
	echo ""
	_info "Running quality checks in test instance..."

	local checks_failed=0

	# Ruff
	_info "▶ Running ruff..."
	if ! uv run ruff check . >/dev/null 2>&1; then
		_error "Ruff check failed"
		checks_failed=1
	else
		_success "Ruff: 0 violations"
	fi

	# MyPy
	_info "▶ Running mypy..."
	if ! uv run mypy "$PROJECT_SLUG" >/dev/null 2>&1; then
		_error "MyPy check failed"
		checks_failed=1
	else
		_success "MyPy: 0 errors"
	fi

	# Pytest
	_info "▶ Running pytest..."
	if ! uv run pytest >/dev/null 2>&1; then
		_error "Pytest failed"
		_warn "Note: Ensure Docker is running for database tests"
		checks_failed=1
	else
		_success "Tests: 100% passing"
	fi

	echo ""

	if [[ $checks_failed -eq 1 ]]; then
		_warn "Quality checks failed - template changes may have issues"
		cd "$TEMPLATE_DIR"
		_info "Template changes:"
		echo ""
		git diff --stat
		echo ""
		read -p "$(echo -e "${YELLOW}?${NC} Commit template changes anyway? (y/n) ")" -n 1 -r response
		echo ""
		if [[ ! $response =~ ^[Yy]$ ]]; then
			_error "Aborting - rolling back template changes"
			git reset --hard HEAD
			return 1
		fi
	fi

	# Success!
	echo ""
	_success "Reverse sync completed successfully!"
	echo ""

	cd "$TEMPLATE_DIR"
	_info "Summary:"
	echo "  Files synced: ${#files_to_sync[@]}"
	echo "  Roundtrip verification: ✓ Passed"
	if [[ $checks_failed -eq 0 ]]; then
		echo "  Quality checks: ✓ Passed"
	else
		_yellow "  Quality checks: ⚠ Failed (review before committing)"
	fi
	echo ""

	_info "Next steps:"
	echo "  1. Review template changes:"
	echo "     git diff"
	echo ""
	echo "  2. Stage and commit:"
	echo "     git add -p"
	echo "     git commit -m 'Fix ruff/mypy errors from test instance'"
	echo ""
	echo "  3. (Optional) Push to remote:"
	echo "     git push"
	echo ""
	_success "Template changes are ready to commit!"

	return 0
}

# ============================================================================
# Clean - Remove test instance
# ============================================================================

_clean() {
	if [[ ! -d "$TEST_INSTANCE_DIR" ]]; then
		_warn "Test instance not found at: $TEST_INSTANCE_DIR"
		return 0
	fi

	_warn "This will permanently delete: $TEST_INSTANCE_DIR"
	if ! _ask_confirmation "Are you sure?"; then
		_info "Clean cancelled"
		return 0
	fi

	_info "Removing test instance..."
	rm -rf "$TEST_INSTANCE_DIR"
	_success "Test instance removed"
}

# ============================================================================
# Shell - Open interactive shell in test instance
# ============================================================================

_shell() {
	if [[ ! -d "$TEST_INSTANCE_DIR" ]]; then
		_error "Test instance not found at: $TEST_INSTANCE_DIR"
		_info "Generate first: $0 generate"
		return 1
	fi

	cd "$TEST_INSTANCE_DIR"

	_info "Opening shell in test instance: $TEST_INSTANCE_DIR"
	_info "Available commands:"
	echo "  - uv run ruff check . → Lint check"
	echo "  - uv run mypy $PROJECT_SLUG → Type checking"
	echo "  - uv run pytest → Run tests"
	echo "  - git status → Check git status"
	echo "  - git log → View commit history"
	echo ""

	bash
}

# ============================================================================
# Help - Display usage information
# ============================================================================

_help() {
	cat <<EOF
FastAPI Template Test Instance Manager

USAGE:
  $0 <command> [options]

COMMANDS:
  generate        Create fresh test instance
  verify          Run quality checks (ruff, mypy, pytest)
  sync            Update from template changes
  reverse-sync    Sync fixes from instance back to template
  clean           Remove test instance
  shell           Open interactive shell in test instance
  help            Show this help message

REVERSE SYNC OPTIONS:
  [--auto]        Skip interactive prompts and sync all changes
  [files...]      Sync only specified files (relative to test instance)

EXAMPLES:
  # First time setup
  $0 generate

  # After making template changes
  $0 sync
  $0 verify

  # After fixing errors in test instance
  $0 reverse-sync                 # Interactive mode - review each file
  $0 reverse-sync --auto          # Auto mode - sync all changes
  $0 reverse-sync file1 file2     # Sync specific files only

  # Debug test instance
  $0 shell

  # Clean up
  $0 clean

TEST INSTANCE:
  Location: $TEST_INSTANCE_DIR
  Project:  $PROJECT_NAME
  Slug:     $PROJECT_SLUG
  Port:     $PORT

FEATURES:
  • Persistent instance with git tracking
  • Bidirectional sync (template ↔ instance)
  • Supports copier update for template syncing
  • Full verification suite (ruff, mypy, pytest)
  • Roundtrip verification for reverse sync
  • Interactive debugging shell

EOF
}

# ============================================================================
# Main Dispatcher
# ============================================================================

main() {
	local command="${1:-help}"

	case "$command" in
	generate)
		_generate
		;;
	verify)
		_verify
		;;
	sync)
		_sync
		;;
	reverse-sync)
		shift  # Remove command, pass remaining args
		_reverse_sync "$@"
		;;
	clean)
		_clean
		;;
	shell)
		_shell
		;;
	help | --help | -h)
		_help
		;;
	*)
		_error "Unknown command: $command"
		_help
		return 1
		;;
	esac
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
	main "$@"
fi
