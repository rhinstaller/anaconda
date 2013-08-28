#!/bin/sh

: "${top_srcdir:=$(dirname "$0")/../..}"
: "${srcdir:=${top_srcdir}/tests/accelerators}"

find "${top_srcdir}" -name '*.glade' -exec "${srcdir}/check_accelerators.py" {} +
