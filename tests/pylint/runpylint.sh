#!/bin/bash

# This script will check anaconda for any pylint warning and errors using a set
# of options minimizing false positives, in combination with filtering of any
# warning regularexpressions listed in pylint-false-positives.
# 
# If any warnings our found they will be stored in pylint-log and printed
# to stdout and this script will exit with a status of 1, if no (non filtered)
# warnings are found it exits with a status of 0

FALSE_POSITIVES=tests/pylint/pylint-false-positives

# W0107 - Unnecessary pass statement
# W0108 - Lambda may not be necessary
# W0212 - Access to a protected member %s of a client class
# W0311 - Bad indentation. Found %s %s, expected %s
# W0312 - Found indentation with %ss instead of %ss
# W0402 - Uses of a deprecated module %r
# W0611 - Unused import %s
# W0612 - Unused variable %r
# W0710 - Exception doesn't inherit from standard "Exception" class
NON_STRICT_OPTIONS="--disable=W0107,W0108,W0212,W0311,W0312,W0402,W0611,W0612,W0710"

# E1103 - %s %r has no %r member (but some types could not be inferred)
DISABLED_ERR_OPTIONS="--disable=E1103"

# W0102 - Dangerous default value %s as argument
# W0141 - Used builtin function %r
# W0142 - Used * or ** magic
# W0201 - Attribute %r defined outside __init__
# W0221 - Arguments number differs from %s method
# W0223 - Method %r is abstract in class %r but is not overridden
# W0231 - __init__ method from base class %r is not called
# W0232 - Class has no __init__ method
# W0233 - __init__ method from a non direct base class %r is called
# W0401 - Wildcard import %s
# W0403 - Relative import %r, should be %r
# W0404 - Reimport %r (imported line %s)
# W0511 - Used when a warning note as FIXME or XXX is detected.
# W0602 - Using global for %r but no assignment is done
# W0603 - Using the global statement
# W0604 - Using the global statement at the module level
# W0613 - Unused argument %r
# W0614 - Unused import %s from wildcard import
# W0621 - Redefining name %r from outer scope (line %s)
# W0622 - Redefining built-in %r
# W0702 - No exception type(s) specified
# W0703 - Catch "Exception"
# W1001 - Use of "property" on an old style class
DISABLED_WARN_OPTIONS="--disable=W0102,W0141,W0142,W0201,W0221,W0223,W0231,W0232 \
                       --disable=W0233,W0401,W0403,W0404,W0511,W0602,W0603,W0604 \
                       --disable=W0613,W0614,W0621,W0622,W0702,W0703,W1001"

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
      sys.path.insert(4, "pyanaconda/.libs"); \
      sys.path.insert(5, "pyanaconda/iw"); \
      sys.path.insert(6, "pyanaconda/textw"); \
      sys.path.insert(7, "/usr/share/system-config-date"); \
      sys.path.insert(8, "/usr/share/system-config-keyboard")' \
    -i y -r n --disable=C,R --rcfile=/dev/null \
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
