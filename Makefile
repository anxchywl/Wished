PYTHON := backend/.venv/bin/python

.PHONY: test lint check deploy

test:
	$(PYTHON) -m pytest backend/tests/ -v --ignore=backend/tests/test_marketplace.py

lint:
	$(PYTHON) -m ruff check backend/

check: lint test

deploy:
	git pull --ff-only
	bash scripts/deploy.sh
