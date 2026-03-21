.PHONY: install dev-install test clean package help

PYTHON := python3
PIP    := pip3

help:
	@echo "El Language — available targets:"
	@echo "  make install      Install via pip (system)"
	@echo "  make dev-install  Install in editable/dev mode"
	@echo "  make test         Run test suite"
	@echo "  make clean        Remove build artefacts and __pycache__"
	@echo "  make package      Build distributable wheel"

install:
	$(PIP) install .

dev-install:
	$(PIP) install -e ".[dev]"

test:
	$(PYTHON) -m pytest tests/ -v --tb=short

test-quick:
	$(PYTHON) -m pytest tests/ -x -q

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf dist/ build/ *.egg-info/ .pytest_cache/ .coverage htmlcov/

package: clean
	$(PYTHON) -m build

run-example:
	$(PYTHON) el_cli.py run examples/01_hello_world.el

run-proof:
	$(PYTHON) el_cli.py run examples/proof_demo.el
