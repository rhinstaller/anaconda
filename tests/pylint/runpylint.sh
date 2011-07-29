#!/bin/bash

# This script will check anaconda for any pylint warning and errors using a set
# of options minimizing false positives, in combination with filtering of any
# warning regularexpressions listed in pylint-false-positives.
# 
# If any warnings our found they will be stored in pylint-log and printed
# to stdout and this script will exit with a status of 1, if no (non filtered)
# warnings are found it exits with a status of 0

FALSE_POSITIVES=tests/pylint/pylint-false-positives
NON_STRICT_OPTIONS="--disable=W0612,W0212,W0312,W0611,W0402,W0108,W0107,W0311,W0710"

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
for i in pyanaconda/storage pyanaconda/installclasses/*.py pyanaconda/iw/*.py pyanaconda/textw/*.py pyanaconda/isys/*.py pyanaconda/; do
  pylint --init-hook='import sys; \
      sys.path.insert(1, "pyanaconda/isys/.libs"); \
      sys.path.insert(2, "pyanaconda/isys"); \
      sys.path.insert(3, "pyanaconda"); \
      sys.path.insert(4, "pyanaconda/.libs"); \
      sys.path.insert(5, "pyanaconda/iw"); \
      sys.path.insert(6, "pyanaconda/textw"); \
      sys.path.insert(7, "/usr/share/system-config-date"); \
      sys.path.insert(8, "/usr/share/system-config-keyboard")' \
    -i y -r n --disable=C,R --rcfile=/dev/null \
    --disable=W0511,W0403,W0703,W0622,W0614,W0401,W0142,W0613,W0621,W0141 \
    --disable=W0102,W0201,W0221,W0702,W0602,W0603,W0604,W1001,W0223 \
    --disable=W0231,W0232,W0233,W0404 \
    --disable=E1103 \
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
