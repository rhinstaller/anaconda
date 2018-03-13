#!/bin/sh

set -- "${top_srcdir}"/tests/rpm_tests

exec nosetests-3 -v --exclude=logpicker -a \!acceptance,\!slow "$@"
