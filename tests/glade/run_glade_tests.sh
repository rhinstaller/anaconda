#!/bin/sh

if ! type parallel 2>&1 > /dev/null; then
    echo "parallel must be installed"
    exit 99
fi

: "${top_srcdir:=$(dirname "$0")/../..}"
. "${top_srcdir}/tests/testenv.sh"
srcdir="${top_srcdir}/tests/glade"
. "${top_srcdir}/tests/lib/testlib.sh"

# If --translated was specified but not --podir, add --podir
translate_set=0
podir_set=0
for arg in "$@" ; do
    if [ "$arg" = "--translate" -o "$arg" = "-t" ]; then
        translate_set=1
    elif echo "$arg" | grep -q '^--podir\(=.*\)\?$' || [ "$arg" = "-p" ]; then
        podir_set=1
    fi
done

if [ "$translate_set" -eq 1 -a "$podir_set" -eq 0 ]; then
    set -- "$@" --podir "${top_srcdir}/po"
fi

status=0
for check in ${srcdir}/*/check_*.py ; do
    findtestfiles -name '*.glade' | parallel --no-notice --gnu -j0 "${check}" "$@" {}
    if [ "$?" -ne 0 ]; then
        status=1
    fi
done

exit $status
