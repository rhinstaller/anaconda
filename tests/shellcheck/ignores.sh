#!/bin/bash
# Paths to ignore in shellcheck tests; these are patterns passed to `grep -v`.
# shellcheck disable=SC2034  # sourced by the unit test script
ignore_patterns=(
dockerfile/
scripts/
widgets/
webui-desktop  # This is just a temporary file, needed to run the Web UI on the Live image, to be replaced with a long term solution eventually
)
