#!/bin/sh

scriptdir="$(dirname "$0")"
gladedir="$scriptdir/../.."

find "${gladedir}" -name '*.glade' -exec "${scriptdir}/check_accelerators.py" {} +
