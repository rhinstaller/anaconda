#!/bin/sh

# If $top_srcdir has not been set by automake, import the test environment
if [ -z "$top_srcdir" ]; then
    top_srcdir="$(realpath "$(dirname "$0")/../..")"
    . "${top_srcdir}/tests/testenv.sh"
fi

# If no tests were selected by user or makefile, select all of them
if [ $# -eq 0 ]; then
    set -- "$top_srcdir/tests/unit_tests"
fi

exec pytest -vv --log-level=NOTSET ${UNIT_TESTS_PATTERN:+-k $UNIT_TESTS_PATTERN} "$@"
