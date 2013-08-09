#!/bin/bash

# This script will check anaconda for any pylint warning and errors using a set
# of options minimizing false positives, in combination with filtering of any
# warning regularexpressions listed in pylint-false-positives.
# 
# If any warnings are found they will be stored in pylint-log and printed
# to stdout and this script will exit with a status of 1, if no (non filtered)
# warnings are found it exits with a status of 0

FALSE_POSITIVES=tests/pylint/pylint-false-positives

# W0212 - Access to a protected member %s of a client class
NON_STRICT_OPTIONS="--disable=W0212"

# E1103 - %s %r has no %r member (but some types could not be inferred)
DISABLED_ERR_OPTIONS="--disable=E1103"

# W0141 - Used builtin function %r
# W0142 - Used * or ** magic
# W0223 - Method %r is abstract in class %r but is not overridden
# W0403 - Relative import %r, should be %r
# W0511 - Used when a warning note as FIXME or XXX is detected.
# W0603 - Using the global statement
# W0613 - Unused argument %r
# W0614 - Unused import %s from wildcard import
DISABLED_WARN_OPTIONS="--disable=W0141,W0142,W0223,W0403,W0511,W0603,W0613,W0614"

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

# run pylint one file / module at a time, otherwise it sometimes gets
# confused
> pylint-log
for i in $(find pyanaconda -type f -name '*py'); do
  pylint --init-hook='import sys; \
      sys.path.insert(1, "pyanaconda/isys/.libs"); \
      sys.path.insert(2, "pyanaconda/isys"); \
      sys.path.insert(3, "pyanaconda"); \
      sys.path.insert(4, "pyanaconda/.libs")' \
    -i y -r n --disable=C,R --rcfile=/dev/null \
    --ignored-classes=Popen,QueueFactory,TransactionSet \
    $DISABLED_WARN_OPTIONS \
    $DISABLED_ERR_OPTIONS \
    $NON_STRICT_OPTIONS $i | \
    egrep -v "`cat $FALSE_POSITIVES | tr '\n' '|'`" > pylint-tmp-log
  if grep -q -v '************* Module ' pylint-tmp-log; then
    cat pylint-tmp-log >> pylint-log
  fi
done
rm pylint-tmp-log

if [ -s pylint-log ]; then
  echo "pylint reports the following issues:"
  cat pylint-log
  exit 1
fi

rm pylint-log

exit 0
