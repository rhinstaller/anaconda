#!/bin/sh

if [ -z "$top_srcdir" ]; then
    echo "*** top_srcdir must be set"
    exit 1
fi

# If no top_builddir is set, use top_srcdir
: "${top_builddir:=$top_srcdir}"

if [ -z "$PYTHONPATH" ]; then
    PYTHONPATH="${top_builddir}/pyanaconda/isys/.libs:${top_srcdir}:${top_srcdir}/tests/lib:${top_srcdir}/dracut"
else
    PYTHONPATH="${PYTHONPATH}:${top_builddir}/pyanaconda/isys/.libs:${top_srcdir}:${top_srcdir}/tests/lib:${top_srcdir}/dracut"
fi

if [ -z "$LD_LIBRARY_PATH" ]; then
    LD_LIBRARY_PATH="${top_builddir}/widgets/src/.libs"
else
    LD_LIBRARY_PATH="${LD_LIBRARY_PATH}:${top_builddir}/widgets/src/.libs"
fi

GI_TYPELIB_PATH="${top_builddir}/widgets/src"
ANACONDA_DATADIR="${top_srcdir}/data"

export ANACONDA_DATADIR
export GI_TYPELIB_PATH
export LD_LIBRARY_PATH
export PYTHONPATH
export top_srcdir
export top_builddir

# Set up the locale.
export LANG=en_US.UTF-8

# This must be added to gi.overrides.__path__ by any test requiring the
# AnacondaWidgets gi-overrides
export ANACONDA_WIDGETS_OVERRIDES="${top_srcdir}/widgets/python"
export UIPATH="${top_srcdir}/pyanaconda/ui/gui/"
export GLADE_CATALOG_SEARCH_PATH="${top_srcdir}/widgets/glade"
export GLADE_MODULE_SEARCH_PATH="${top_builddir}/widgets/src/.libs"
export ANACONDA_DATA="${top_srcdir}/data"

# Use the default configuration in tests.
export ANACONDA_CONFIG_TMP="${top_srcdir}/data/anaconda.conf"
