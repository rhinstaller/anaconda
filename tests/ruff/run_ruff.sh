#!/bin/bash

# If $top_srcdir has not been set by automake, detect it
if [ -z "$top_srcdir" ]; then
    top_srcdir="$(realpath "$(dirname "$0")/../..")"
fi

ruff --version

ruff check \
  --fix \
  --config "$top_srcdir/tests/ruff/ruff.toml" \
  "$top_srcdir/pyanaconda/" \
  "$top_srcdir/tests/" \
  "$top_srcdir/scripts/" \
