#!/bin/bash

# If $top_srcdir has not been set by automake, detect it
if [ -z "$top_srcdir" ]; then
    top_srcdir="$(realpath "$(dirname "$0")/../..")"
fi

source "${top_srcdir}/tests/shellcheck/ignores.sh"

# Check if this test can be run
if ! type shellcheck > /dev/null 2>&1 ; then
    echo "SKIP - shellcheck must be installed to run it."
    exit 77
fi

# Identify which shellcheck version is running to debug fails due to version bump
shellcheck --version
rpm -q ShellCheck
echo

# Ignore files according to path patterns
pushd "${top_srcdir}" > /dev/null || return 1
files=$(git ls-files)
# shellcheck disable=SC2154  # comes from the file sourced earlier
for ignore in "${ignore_patterns[@]}" ; do
    files=$(echo "$files" | grep -v "$ignore")
done

# Find files that are shell scripts
files=$(echo "$files" | xargs file | grep "shell script" | awk -F ":" '{print $1}')

# List files being checked
echo -e "Files to be checked:\n--------------------\n$files\n"

# Do the actual linting
echo -e "Warnings found:\n---------------"
if ! echo "$files" | xargs shellcheck -f gcc ; then
  exit 1
fi
