#!/bin/bash

# If $top_srcdir has not been set by automake, detect it
if [ -z "$top_srcdir" ]; then
    top_srcdir="$(realpath "$(dirname "$0")/../..")"
fi

ruff --version

ruff check "$top_srcdir"
