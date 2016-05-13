#!/bin/sh -e
# Run the translation-canary tests on translatable strings.

# If not run from automake, fake it
if [ -z "$top_srcdir" ]; then
    top_srcdir="$(dirname "$0")/../.."
fi

. "${top_srcdir}/tests/testenv.sh"

# Make sure anaconda.pot is update to date
make -C ${top_builddir}/po anaconda.pot-update >/dev/null 2>&1

PYTHONPATH="${PYTHONPATH}:${top_srcdir}/translation-canary"
export PYTHONPATH

# Run the translatable tests on the POT file
python3 -m translation_canary.translatable "${top_builddir}/po/anaconda.pot"
