#!/bin/bash
# Paths to ignore in shellcheck tests; these are patterns passed to `grep -v`.
# shellcheck disable=SC2034  # sourced by the unit test script
ignore_patterns=(
dockerfile/
scripts/
widgets/
webui-desktop  # This is just a temporary file, to be replaced with cockpit-desktop once 'unshare' is not filtered out by lorax
)
