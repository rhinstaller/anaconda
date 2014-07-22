#!/bin/sh

# If $top_srcdir has not been set by automake, import the test environment
if [ -z "$top_srcdir" ]; then
    top_srcdir="$(dirname "$0")/.."
    . ${top_srcdir}/tests/testenv.sh
fi

# If no tests were selected, select all of them
if [ $# -eq 0 ]; then
    set -- "${top_srcdir}"/tests/*_tests
fi

exec nosetests -v --exclude=logpicker -a \!acceptance,\!slow "$@"
