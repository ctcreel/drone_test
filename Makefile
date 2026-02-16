.PHONY: install lint lint-quick test test-edge check check-all format security naming cdk-synth cdk-diff cdk-deploy deploy edge-test integration-test help run dev

# Colors for output
BLUE := \033[0;34m
YELLOW := \033[0;33m
RED := \033[0;31m
GREEN := \033[0;32m
NC := \033[0m # No Color

# Use external SSD for temp files if available (avoids ENOSPC on internal drive)
SSD_TMP := /Volumes/SSD/tmp
export TMPDIR := $(if $(wildcard $(SSD_TMP)),$(SSD_TMP),$(TMPDIR))

# ═══════════════════════════════════════════════════════════════════════════
# SETUP
# ═══════════════════════════════════════════════════════════════════════════

install: ## Install all dependencies
	uv sync --all-extras

# ═══════════════════════════════════════════════════════════════════════════
# LINTING & TYPE CHECKING
# ═══════════════════════════════════════════════════════════════════════════

lint-quick: ## Quick lint checks (ruff + pyright only)
	@echo "$(BLUE)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"
	@echo "$(BLUE)Running quick lint checks...$(NC)"
	@echo "$(BLUE)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"
	uv run ruff check src/ infra/ edge/
	uv run pyright src/ infra/
	@echo "$(GREEN)Quick lint passed$(NC)"

lint: lint-quick ## Full lint checks (ruff + pyright + format check + vulture)
	uv run ruff format --check src/ infra/ edge/
	uv run vulture src/
	@echo "$(GREEN)Full lint passed$(NC)"

# ═══════════════════════════════════════════════════════════════════════════
# TESTING
# ═══════════════════════════════════════════════════════════════════════════

test: ## Run cloud tier tests with 95% coverage requirement
	uv run pytest --cov=src --cov-fail-under=95 --cov-report=term-missing --cov-report=xml tests/

test-edge: ## Run edge tier tests
	uv run pytest --cov=edge --cov-fail-under=95 --cov-report=term-missing edge_tests/

test-infra: ## Run CDK infrastructure tests
	PYTHONPATH=infra uv run pytest infra_tests/ --no-cov -q

test-all: test test-edge test-infra ## Run all test suites

integration-test: ## Run integration tests against simulation
	uv run pytest integration_tests/ -v --timeout=300

# ═══════════════════════════════════════════════════════════════════════════
# SECURITY & NAMING CHECKS
# ═══════════════════════════════════════════════════════════════════════════

security: ## Run security checks (bandit + pip-audit)
	uv run bandit -r src/ edge/
	uv run pip-audit

naming: ## Check naming conventions, abbreviations, imports, and skip comments
	@echo "$(BLUE)Checking naming conventions...$(NC)"
	uv run python scripts/check_naming_conventions.py
	uv run python scripts/check_abbreviations.py
	uv run python scripts/check_imports.py
	uv run python scripts/check_skip_comments.py
	scripts/check_branch_name.sh
	@echo "$(GREEN)Naming checks passed$(NC)"

# ═══════════════════════════════════════════════════════════════════════════
# COMBINED CHECKS
# ═══════════════════════════════════════════════════════════════════════════

check: lint test security naming ## Run ALL checks (lint + test + security + naming)
	@echo "$(GREEN)All local checks passed$(NC)"

# ═══════════════════════════════════════════════════════════════════════════
# FORMATTING
# ═══════════════════════════════════════════════════════════════════════════

format: ## Auto-fix lint issues and format code
	uv run ruff check --fix src/ infra/ edge/
	uv run ruff format src/ infra/ edge/
	@echo "$(GREEN)Code formatted$(NC)"

# ═══════════════════════════════════════════════════════════════════════════
# CDK / INFRASTRUCTURE
# ═══════════════════════════════════════════════════════════════════════════

cdk-synth: ## Synthesize CDK CloudFormation templates
	cd infra && uv run cdk synth

cdk-diff: ## Show CDK deployment diff
	cd infra && uv run cdk diff

cdk-deploy: check cdk-synth ## Deploy CDK (requires all checks to pass)
	cd infra && uv run cdk deploy --all --require-approval never

deploy: cdk-deploy ## Alias for cdk-deploy

# ═══════════════════════════════════════════════════════════════════════════
# HELP
# ═══════════════════════════════════════════════════════════════════════════

help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-20s$(NC) %s\n", $$1, $$2}'
