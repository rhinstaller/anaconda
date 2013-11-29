#!/bin/sh

: "${top_srcdir:=$(dirname "$0")/../..}"
srcdir="${top_srcdir}/tests/glade/pw_visibility"

find "${top_srcdir}/pyanaconda" -name '*.glade' -exec "${srcdir}/check_pw_visibility.py" "$@" {} +
