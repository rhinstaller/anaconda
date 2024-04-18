#!/bin/bash

# Run vulture but ignore the following files:
# - unit_tests: These contain many false positives because of the mock library
EXCLUDE_PATTERNS="*unit_tests*"

IGNORE_NAMES="""
option_string # Used when creating custom actions for argparse
"""
# replace new line with commas and delete comments
IGNORE_NAMES=$(echo "$IGNORE_NAMES" | tr '\n' ',' | sed 's/#.*//')

find_scripts() {
    # Helper to find all scripts in the tree
    (
        # Any non-binary file which contains a given shebang
        git grep --cached -lIz '^#!.*'"$1"
        shift
        # Any file matching the provided globs
        git ls-files -z "$@"
    ) | sort -z | uniq -z
}

find_python_files() {
    find_scripts 'python3' '*.py'
}

skip() {
    printf "%s\n" "$*"
    exit 77
}

python3 -c 'import vulture' 2>/dev/null || skip 'no python3-vulture'
find_python_files | xargs -r -0 python3 -m vulture \
    --min-confidence "${VULTURE_CONFIDENCE:-100}" \
    --exclude "$EXCLUDE_PATTERNS" \
    --ignore-names "$IGNORE_NAMES"
