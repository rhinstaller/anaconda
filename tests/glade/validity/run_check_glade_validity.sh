#!/bin/sh

if [ -z "$top_srcdir" ]; then
    top_srcdir="$(dirname "$0")/../../.."
    . "${top_srcdir}/tests/testenv.sh"
fi

srcdir="${top_srcdir}/tests/glade/validity"

find "${top_srcdir}" -name '*.glade' -exec "${srcdir}/check_glade_validity.py" "$@" {} +
