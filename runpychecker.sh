#!/bin/bash

FALSE_POSITIVES=pychecker-false-positives

if [ "`tail -c 1 pychecker-false-positives`" == "`echo`" ]; then
  echo "Error $FALSE_POSITIVES ends with an enter."
  echo "Error the last line of $FALSE_POSITIVES should never have an enter!"
  exit 1
fi

export PYTHONPATH="isys:textw:iw:installclasses:/usr/lib/booty"

pychecker --only --limit 1000 \
  --maxlines 500 --maxargs 20 --maxbranches 80 --maxlocals 60 --maxreturns 20 \
  --no-callinit --no-local --no-shadow --no-shadowbuiltin \
  --no-import --no-miximport --no-pkgimport --no-reimport \
  --no-argsused --no-varargsused --no-override \
  anaconda anaconda *.py textw/*.py iw/*.py installclasses/*.py isys/*.py | \
  egrep -v "`cat $FALSE_POSITIVES | tr '\n' '|'`" > pychecker-log

if [ -s pychecker-log ]; then
  echo "Pychecker reports the following issues:"
  cat pychecker-log
  exit 1
fi

rm pychecker-log

exit 0
