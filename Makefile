PYTHONPATH ?= packages

.PHONY: test unit cov clean

test:
	PYTHONPATH=$(PYTHONPATH) pytest -v --tb=short

unit:
	PYTHONPATH=$(PYTHONPATH) pytest -m unit -v --tb=short

cov:
	PYTHONPATH=$(PYTHONPATH) pytest -v --tb=short --cov=packages --cov-report=term-missing --cov-fail-under=80

clean:
	rm -rf .pytest_cache .coverage htmlcov
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +

