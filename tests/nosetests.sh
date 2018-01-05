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

# FIXME: remove the dd_test exclude when the python3-rpmfluff package will be available
exec nosetests-3 -v --exclude=logpicker --exclude=dd_test* -a \!acceptance,\!slow "$@"
