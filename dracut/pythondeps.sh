#!/bin/bash

python="python"

eval $($python << _EOT_
from distutils.sysconfig import *
print 'makefile=' + get_makefile_filename()
print 'config_h=' + get_config_h_filename()
print 'sitedir=' + get_python_lib()
_EOT_
)
libdir=${makefile%/config/Makefile}

pydeps() {
    echo $makefile
    echo $config_h
    while [ $# -gt 0 ]; do
        $python -v $1 2>&1 | sed -ne 's/^import.* from //p'
        shift
    done
}

# basedir /path/top/module/sub/filename.py /path/top -> /path/top/module
basedir() { mod=${1#$2/}; mod=${mod%%/*}; echo $2/$mod; }

pydeps "$@" | sed 's/\.py[coO]$/.py/' | sort -u | while read dep; do
  case "$dep" in
    $sitedir/*/*.py) find "$(basedir $dep $sitedir)" -type f ;;
    $libdir/*/*.py) find "$(basedir $dep $libdir)" -type f ;;
    *) echo $dep ;;
  esac
done | grep -v '\.py[coO]' | sort -u
