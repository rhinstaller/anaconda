#!/bin/bash
# Paths to ignore in shellcheck tests; these are patterns passed to `grep -v`.
# shellcheck disable=SC2034  # sourced by the unit test script
ignore_patterns=(
dockerfile/
scripts/
widgets/
)
