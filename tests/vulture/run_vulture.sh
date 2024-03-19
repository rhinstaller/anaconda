#!/bin/bash

# Run vulture but ignore the following files:
# - unit_tests: These contain many false positives because of the mock library
EXCLUDE_PATTERNS="*unit_tests*"

IGNORE_NAMES="""
option_string # Used when creating custom actions for argparse
"""
# replace new line with commas and delete comments
IGNORE_NAMES=$(echo "$IGNORE_NAMES" | tr '\n' ',' | sed 's/#.*//')

# If $top_srcdir has not been set by automake, import the test environment
if [ -z "$top_srcdir" ]; then
    top_srcdir="$(realpath "$(dirname "$0")/../..")"
    . "${top_srcdir}/tests/testenv.sh"
fi

exec python3 -m vulture "$top_srcdir" \
    --min-confidence "${VULTURE_CONFIDENCE:-100}" \
    --exclude "$EXCLUDE_PATTERNS" \
    --ignore-names "$IGNORE_NAMES"
