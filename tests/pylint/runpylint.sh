#!/bin/bash

# This script will check anaconda for any pylint warning and errors using a set
# of options minimizing false positives, in combination with filtering of any
# warning regularexpressions listed in pylint-false-positives.
# 
# If any warnings are found they will be stored in pylint-log and printed
# to stdout and this script will exit with a status of 1, if no (non filtered)
# warnings are found it exits with a status of 0

if ! type parallel 2>&1 > /dev/null; then
    echo "parallel must be installed"
    exit 99
fi

# XDG_RUNTIME_DIR is "required" to be set, so make one up in case something
# actually tries to do something with it
if [ -z "$XDG_RUNTIME_DIR" ]; then
    export XDG_RUNTIME_DIR="$(mktemp -d)"
    trap "rm -rf \"$XDG_RUNTIME_DIR\"" EXIT
fi

# If $top_srcdir is set, assume this is being run from automake and we don't
# need to keep a separate log
export pylint_log=0
if [ -z "$top_srcdir" ]; then
    export pylint_log=1
fi

# Unset TERM so that things that use readline don't output terminal garbage
unset TERM

# Don't try to connect to the accessibility socket
export NO_AT_BRIDGE=1

# Force the GDK backend to X11. Otherwise if no display can be found, Gdk
# tries every backend type, which includes "broadway," which prints an error
# and keeps changing the content of said error.
export GDK_BACKEND=x11

# If $top_srcdir has not been set by automake, import the test environment
if [ -z "$top_srcdir" ]; then
    top_srcdir="$(dirname "$0")/../.."
    . ${top_srcdir}/tests/testenv.sh
fi

. ${top_srcdir}/tests/lib/testlib.sh

srcdir="${top_srcdir}/tests/pylint"
builddir="${top_builddir}/tests/pylint"

# Need to add the pylint module directory to PYTHONPATH as well.
export PYTHONPATH="${PYTHONPATH}:${srcdir}"

# Save analysis data in the pylint directory
export PYLINTHOME="${builddir}/.pylint.d"
[ -d "$PYLINTHOME" ] || mkdir "$PYLINTHOME"

export FALSE_POSITIVES="${srcdir}"/pylint-false-positives

# W0212 - Access to a protected member %s of a client class
export NON_STRICT_OPTIONS="--disable=W0212"

# E1103 - %s %r has no %r member (but some types could not be inferred)
export DISABLED_ERR_OPTIONS="--disable=E1103"

# W0110 - map/filter on lambda could be replaced by comprehension
# W0123 - Use of eval
# W0141 - Used builtin function %r
# W0142 - Used * or ** magic
# W0511 - Used when a warning note as FIXME or XXX is detected.
# W0603 - Using the global statement
# W0613 - Unused argument %r
# W0614 - Unused import %s from wildcard import
# I0011 - Locally disabling %s (i.e., pylint: disable)
# I0012 - Locally enabling %s (i.e., pylint: enable)
# I0013 - Ignoring entire file (i.e., pylint: skip-file)
export DISABLED_WARN_OPTIONS="--disable=W0110,W0123,W0141,W0142,W0511,W0603,W0613,W0614,I0011,I0012,I0013"

# string is about half-deprecated, so add it to the list of deprecated modules
# and handle the valid cases with pragma comments.
export EXTRA_OPTIONS="--deprecated-modules=string,regsub,TERMIOS,Bastion,rexec"

usage () {
  echo "usage: `basename $0` [--strict] [--help] [files...]"
  exit $1
}

# Separate the module parameters from the files list
ARGS=
FILES=
while [ $# -gt 0 ]; do
  case $1 in
    --strict)
      export NON_STRICT_OPTIONS=
      ;;
    --help)
      usage 0
      ;;
    -*)
      ARGS="$ARGS $1"
      ;;
    *)
      FILES=$@
      break
  esac
  shift
done

exit_status=0

if [ -s pylint-log ]; then
    rm pylint-log
fi

# run pylint one file / module at a time, otherwise it sometimes gets
# confused
if [ -z "$FILES" ]; then
    # Test any file that either ends in .py or contains #!/usr/bin/python2 in
    # the first line.  Scan everything except old_tests
    FILES=$(findtestfiles \( -name '*.py' -o \
                -exec /bin/sh -c "head -1 {} | grep -q '#!/usr/bin/python2'" \; \) -print | \
            egrep -v '(|/)old_tests/')
fi

# run pylint in paralel
output=$(echo -n $FILES | parallel --no-notice -d' ' --gnu "$srcdir"/pylint-one.sh $ARGS {})
exit_status=$?

if [ "$output" != '\n' -a "$output" != "" ]; then
    echo "pylint reports the following issues:"
    echo "$output" | tee pylint-log
fi

exit "$exit_status"
