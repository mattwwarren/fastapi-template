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
  $0 <command>

COMMANDS:
  generate    Create fresh test instance
  verify      Run quality checks (ruff, mypy, pytest)
  sync        Update from template changes
  clean       Remove test instance
  shell       Open interactive shell in test instance
  help        Show this help message

EXAMPLES:
  # First time setup
  $0 generate

  # After making template changes
  $0 sync
  $0 verify

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
  • Supports copier update for template syncing
  • Full verification suite (ruff, mypy, pytest)
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
