#!/bin/sh

# If $top_srcdir has not been set by automake, import the test environment
if [ -z "$top_srcdir" ]; then
    top_srcdir="$(dirname "$0")/../.."
    . ${top_srcdir}/tests/testenv.sh
fi

. ${top_srcdir}/tests/lib/testlib.sh

if ! type cppcheck > /dev/null 2>&1 ; then
    echo "cppcheck must be installed"
    exit 99
fi

# If files were specified on the command line, use those. Otherwise, look
# for all .c files
filelist=
if [ "$#" -gt 0 ]; then
    filelist="$@"
else
    filelist=$(findtestfiles -name '*.c')
fi

# Disable unusedFunction in widgets since everything will show up as unused
# Specify the path twice so the path works relative to both the top of the
# tree and from the tests/ directory.
cppcheck_output="$(echo "$filelist" |
    xargs cppcheck -q -v --error-exitcode=1 \
        --template='{id}:{file}:{line}: {message}' \
        --inline-suppr \
        --enable=warning,unusedFunction \
        --suppress=unusedFunction:*/widgets/src/* \
        --suppress=unusedFunction:widgets/src/* \
        2>&1 )"

if [ -n "$cppcheck_output" ]; then
    echo "$cppcheck_output"
    exit 1
fi
