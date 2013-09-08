#!/bin/sh

if [ -z "$top_srcdir" ]; then
    echo "*** top_srcdir must be set"
    exit 1
fi

# If not top_builddir is set, use top_srcdir
: "${top_builddir:=$top_srcdir}"

PYTHONPATH="${top_builddir}/pyanaconda/isys/.libs:${top_srcdir}/pyanaconda:${top_srcdir}"
export PYTHONPATH
export top_srcdir
export top_builddir
