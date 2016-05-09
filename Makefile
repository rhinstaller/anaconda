# This Makefile is just for running the tests

all:
	@echo "nothing to build"

check:
	PYTHONPATH=. tests/pylint/runpylint.py
	python3 -m unittest discover tests/unittests

test-projects:
	PYTHONPATH=. tests/project-tests/test_projects.sh tests/project-tests/project_list.txt

ci:
	$(MAKE) check
