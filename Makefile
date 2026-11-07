# One-word lowercase targets, `help` first. See the makefile-standards skill.

.DEFAULT_GOAL := help
.PHONY: help test lint fmt install clean public

help: ## show this help
	@awk 'BEGIN {FS = ":.*?## "; printf "\n\033[1mUsage:\033[0m make \033[36m<target>\033[0m\n\n\033[1mTargets:\033[0m\n"} \
	     /^[a-z]+:.*?## / {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2} \
	     END {print ""}' $(MAKEFILE_LIST)

test: ## run the test suite
	@uv run pytest -q

lint: ## ruff format check + ruff lint
	@uv run ruff format --check .
	@uv run ruff check .

fmt: ## format with ruff
	@uv run ruff format .
	@uv run ruff check --fix .

install: ## install vedit on PATH (editable)
	@uv tool install -e . --force

clean: ## remove caches and build output, print what was freed
	@bash scripts/clean.sh

public: ## export a scrubbed single-commit tree for the public repo (no personal data)
	@bash scripts/public.sh $${OUT:-.public}
