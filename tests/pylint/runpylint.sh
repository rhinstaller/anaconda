#!/bin/bash

# This script will check anaconda for any pylint warning and errors using a set
# of options minimizing false positives, in combination with filtering of any
# warning regularexpressions listed in pylint-false-positives.
# 
# If any warnings are found they will be stored in pylint-log and printed
# to stdout and this script will exit with a status of 1, if no (non filtered)
# warnings are found it exits with a status of 0

# If $top_srcdir is set, assume this is being run from automake and we don't
# need to keep a separate log
pylint_log=0
if [ -z "$top_srcdir" ]; then
    pylint_log=1
fi

: "${top_srcdir:=$(dirname "$0")/../..}"
: "${srcdir:=${top_srcdir}/tests/pylint}"

FALSE_POSITIVES="${srcdir}"/pylint-false-positives

# W0212 - Access to a protected member %s of a client class
NON_STRICT_OPTIONS="--disable=W0212"

# E1103 - %s %r has no %r member (but some types could not be inferred)
DISABLED_ERR_OPTIONS="--disable=E1103"

# W0110 - map/filter on lambda could be replaced by comprehension
# W0141 - Used builtin function %r
# W0142 - Used * or ** magic
# W0223 - Method %r is abstract in class %r but is not overridden
# W0403 - Relative import %r, should be %r
# W0511 - Used when a warning note as FIXME or XXX is detected.
# W0603 - Using the global statement
# W0604 - Using the global statement at the module level
# W0613 - Unused argument %r
# W0614 - Unused import %s from wildcard import
DISABLED_WARN_OPTIONS="--disable=W0110,W0141,W0142,W0223,W0403,W0511,W0603,W0604,W0613,W0614"

usage () {
  echo "usage: `basename $0` [--strict] [--help]"
  exit $1
}

while [ $# -gt 0 ]; do
  case $1 in
    --strict)
      NON_STRICT_OPTIONS=
      ;;
    --help)
      usage 0
      ;;
    *)
      echo "Error unknown option: $1"
      usage 1
  esac
  shift
done

if [ "`tail -c 1 $FALSE_POSITIVES`" == "`echo`" ]; then
  echo "Error $FALSE_POSITIVES ends with an enter."
  echo "Error the last line of $FALSE_POSITIVES should never have an enter!"
  exit 1
fi

exit_status=0
if [ "$pylint_log" -ne 0 ]; then
    > pylint-log
fi

# run pylint one file / module at a time, otherwise it sometimes gets
# confused
for i in "${top_srcdir}"/anaconda $(find "${top_srcdir}/pyanaconda" -type f -name '*py' \! -executable); do
  if [ -n "$(echo "$i" | grep 'pyanaconda/packaging/dnfpayload.py$')" ]; then
     continue
  fi

  pylint_output="$(pylint \
    --msg-template='{msg_id}:{line:3d},{column}: {obj}: {msg}' \
    -r n --disable=C,R --rcfile=/dev/null \
    --dummy-variables-rgx=_ \
    --ignored-classes=DefaultInstall,Popen,QueueFactory,TransactionSet \
    --defining-attr-methods=__init__,_grabObjects,initialize,reset,start \
    $DISABLED_WARN_OPTIONS \
    $DISABLED_ERR_OPTIONS \
    $NON_STRICT_OPTIONS $i | \
    egrep -v "$(tr '\n' '|' < "$FALSE_POSITIVES") \
    ")"
  # I0011 is the informational "Locally disabling ...." message
  if [ -n "$(echo "$pylint_output" | fgrep -v '************* Module ' |\
          grep -v '^I0011:')" ]; then
      if [ "$pylint_log" -ne 0 ]; then
          echo "$pylint_output" >> pylint-log
      else
          echo "$pylint_output"
      fi
      exit_status=1
  fi
done

if [ "$pylint_log" -ne 0 ]; then
    if [ -s pylint-log ]; then
        echo "pylint reports the following issues:"
        cat pylint-log
    else
        rm pylint-log
    fi
fi

exit "$exit_status"
