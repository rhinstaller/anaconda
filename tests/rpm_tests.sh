#!/bin/sh

# If no tests were selected by user or makefile, select all of them
if [ $# -eq 0 ] && [ -z $RPM_TESTS_ARGS ]; then
    set -- "${top_srcdir}"/tests/rpm_tests
fi

exec nosetests-3 -v --exclude=logpicker -a \!acceptance,\!slow $RPM_TESTS_ARGS "$@"
