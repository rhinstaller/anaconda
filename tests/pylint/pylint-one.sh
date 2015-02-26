#!/bin/bash
#
# $1 -- python source to run pylint on
#

if [ $# -lt 1 ]; then
    # no source, just exit
    exit 1
fi

if grep -q '# pylint: skip-file' $1; then
    exit 0
fi

pylint_output="$(pylint \
    --msg-template='{msg_id}:{line:3d},{column}: {obj}: {msg}' \
    -r n --disable=C,R --rcfile=/dev/null \
    --dummy-variables-rgx=_ \
    --ignored-classes=DefaultInstall,Popen,QueueFactory,TransactionSet \
    --defining-attr-methods=__init__,_grabObjects,initialize,reset,start,setUp \
    --load-plugins=intl,preconf,markup,eintr,pointless-override,environ \
    --init-import=y \
    --init-hook=\
'import gi.overrides, os;
gi.overrides.__path__[0:0] = (os.environ["ANACONDA_WIDGETS_OVERRIDES"].split(":") if "ANACONDA_WIDGETS_OVERRIDES" in os.environ else [])' \
    $DISABLED_WARN_OPTIONS \
    $DISABLED_ERR_OPTIONS \
    $EXTRA_OPTIONS \
    $NON_STRICT_OPTIONS "$@" 2>&1 | \
    egrep -v -f "$FALSE_POSITIVES" \
    )"

if [ -n "$(echo "$pylint_output" | fgrep -v '************* Module ')" ]; then
    # Replace the Module line with the actual filename
    pylint_output="$(echo "$pylint_output" | sed "s|\* Module .*|* Module $(eval echo \$$#)|")"
    echo "$pylint_output"
    exit 1
else
    exit 0
fi
