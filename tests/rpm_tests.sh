#!/bin/sh

# If $top_srcdir has not been set by automake, import the test environment
if [ -z "$top_srcdir" ]; then
    top_srcdir="$(realpath $(dirname "$0")/..)"
    . ${top_srcdir}/tests/testenv.sh
fi

# If no tests were selected by user or makefile, select all of them
if [ $# -eq 0 ]; then
    set -- "${top_srcdir}"/tests/rpm_tests
fi

# TODO: RPM_TESTS_ARGS are not usable in the container environment. Do we want to keep it?
# That variable is not propagated from Makefile which is because the way the test is executed.
exec python3 -m unittest discover -t $top_srcdir -v -b ${RPM_TESTS_ARGS:+-k} $RPM_TESTS_ARGS -s $@
