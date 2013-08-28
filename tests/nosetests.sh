#!/bin/sh

echo $PYTHONPATH

# Use the directory above the one containing the script as the default for
# $top_srcdir
: "${top_srcdir:=$(dirname "$0")/..}"

# If no tests were selected, select all of them
if [ $# -eq 0 ]; then
    set -- "${top_srcdir}"/tests/*_tests
fi

exec nosetests -v --exclude=logpicker -a \!acceptance,\!slow "$@"
