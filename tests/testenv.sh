#!/bin/sh

if [ -z "$top_srcdir" ]; then
    echo "*** top_srcdir must be set"
    exit 1
fi

# If no top_builddir is set, use top_srcdir
: "${top_builddir:=$top_srcdir}"

if [ -z "$PYTHONPATH" ]; then
    PYTHONPATH="${top_builddir}/pyanaconda/isys/.libs:${top_srcdir}/pyanaconda:${top_srcdir}"
else
    PYTHONPATH="${PYTHONPATH}:${top_builddir}/pyanaconda/isys/.libs:${top_srcdir}/pyanaconda:${top_srcdir}"
fi

ANACONDA_INSTALL_CLASSES="${top_builddir}/pyanaconda/installclasses"

export ANACONDA_INSTALL_CLASSES
export PYTHONPATH
export top_srcdir
export top_builddir
