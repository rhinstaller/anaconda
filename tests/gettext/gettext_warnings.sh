#!/bin/sh -e

if [ -z "$top_srcdir" ]; then
    top_srcdir="$(dirname "$0")/../.."
    . "${top_srcdir}/tests/testenv.sh"
fi
podir="${top_builddir}/po"
POTFILES="${podir}/POTFILES"

# Extract XGETTEXT_OPTIONS from po/Makevars
# Makevars is one of our files, so it's in $srcdir
XGETTEXT_OPTIONS="$(sed -n 's/^[[:space:]]*XGETTEXT_OPTIONS[[:space:]]*=[[:space:]]*\(.*\)/\1/p' \
    "${top_srcdir}/po/Makevars")"

# Fail if POTFILES doesn't exist, since set -e doesn't catch this for some
# dumb reason that I'm sure has a long and storied history
if [ ! -f "${POTFILES}" ] ; then
    echo "POTFILES does not exist"
    exit 1
fi

status=0
# For each file in POTFILES, run xgettext and look for warnings
while read -r potfile ; do
    # Strip the spaces and trailing backslash
    potfile="$(echo "$potfile" | sed 's/^[[:space:]]*\([^[:space:]]*\)[[:space:]]*\\\?$/\1/')"

    # $potfile is relative to the po/ directory, $test_potfile is
    # relative to this script's working directory
    test_potfile="${podir}/${potfile}"

    # If the file doesn't exist, try to make it
    if [ ! -f "$test_potfile" ]; then
        make -C "${podir}" "${potfile}" || exit 1
    fi

    xgettext_output="$(xgettext ${XGETTEXT_OPTIONS} -o /dev/null "$test_potfile" 2>&1)" || status=1
    if echo "$xgettext_output" | fgrep -q 'warning:' ; then
        echo "$xgettext_output"
        status=1
    fi
done < "$POTFILES"

exit "$status"
