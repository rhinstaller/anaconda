#!/bin/bash

# This script will check anaconda for any pychecker warning using a set of
# options minimizing false positives, in combination with filtering of any
# warning regularexpressions listed in pychecker-false-positives.
# 
# If any warnings our found they will be stored in pychecker-log and printed
# to stdout and this script will exit with a status of 1, if no (non filtered)
# warnings are found it exits with a status of 0

FALSE_POSITIVES=pychecker-false-positives
NON_STRICT_OPTIONS="--no-deprecated --no-returnvalues --no-abstract"

usage () {
  echo "usage: `basename $0` [--strict] [--help]"
  exit $1
}

while [ $# -gt 0 ]; do
  case $1 in
    --strict)
      NON_STRICT_OPTIONS=""
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

if [ "`tail -c 1 pychecker-false-positives`" == "`echo`" ]; then
  echo "Error $FALSE_POSITIVES ends with an enter."
  echo "Error the last line of $FALSE_POSITIVES should never have an enter!"
  exit 1
fi

export PYTHONPATH=".:.libs:isys:isys/.libs:textw:iw:installclasses:/usr/share/system-config-date"

pychecker --only --limit 1000 \
  --maxlines 500 --maxargs 20 --maxbranches 80 --maxlocals 60 --maxreturns 20 \
  --no-callinit --no-local --no-shadow --no-shadowbuiltin \
  --no-import --no-miximport --no-pkgimport --no-reimport \
  --no-argsused --no-varargsused --no-override \
  $NON_STRICT_OPTIONS \
  anaconda anaconda *.py textw/*.py iw/*.py installclasses/*.py isys/*.py booty/*.py booty/*/*.py | \
  egrep -v "`cat $FALSE_POSITIVES | tr '\n' '|'`" > pychecker-log

if [ -s pychecker-log ]; then
  echo "Pychecker reports the following issues:"
  cat pychecker-log
  exit 1
fi

rm pychecker-log

exit 0
