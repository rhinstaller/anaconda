#!/bin/sh

# If $top_srcdir has not been set by automake, import the test environment
if [ -z "$top_srcdir" ]; then
    top_srcdir="$(dirname "$0")/.."
    . ${top_srcdir}/tests/testenv.sh
fi

# If no tests were selected by user or makefile, select all of them
if [ $# -eq 0 ] && [ -z $NOSE_TESTS_ARGS ]; then
    set -- "${top_srcdir}"/tests/nosetests/*_tests
fi

exec python3 -m nose -v --exclude=logpicker -a \!acceptance,\!slow $NOSE_TESTS_ARGS "$@"
