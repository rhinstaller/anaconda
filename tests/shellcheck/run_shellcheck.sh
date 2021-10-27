#!/bin/bash

# If $top_srcdir has not been set by automake, import the test environment
if [ -z "$top_srcdir" ]; then
    top_srcdir="$(realpath "$(dirname "$0")/../..")"
    . "${top_srcdir}"/tests/testenv.sh
fi

# check if this test can be run
if ! type shellcheck > /dev/null 2>&1 ; then
    echo "SKIP - shellcheck must be installed to run it."
    exit 77
fi

pushd "${top_srcdir}" > /dev/null || return 1

error=0

for file in $(git ls-files) ; do
    if file "$file" | grep "shell script" >/dev/null ; then
        if ! shellcheck -e SC2230 "$file" ; then
            error=1
        fi
    fi
done;

exit $error
