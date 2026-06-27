PYTHON := backend/.venv/bin/python

.PHONY: test lint check deploy

test:
	$(PYTHON) -m pytest backend/tests/ -v

lint:
	$(PYTHON) -m ruff check backend/

check: lint test

deploy:
	git stash push --include-untracked -m "pre-deploy $$(date -u +%Y-%m-%dT%H:%M:%SZ)" || true
	git pull --ff-only
	bash scripts/deploy.sh
