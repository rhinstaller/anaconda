# This Makefile is just for running the tests

all:
	@echo "nothing to build"

check:
	PYTHONPATH=. tests/pylint/runpylint.py
	python3 -m unittest discover tests/unittests

ci:
	$(MAKE) check
