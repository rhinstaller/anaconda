#!/bin/bash

# If $top_srcdir has not been set by automake, import the test environment
if [ -z "$top_srcdir" ]; then
    top_srcdir="$(dirname "$0")/../.."
fi

. ${top_srcdir}/tests/testenv.sh
. ${top_srcdir}/tests/pep8/config.target

pep8_command=""
for cmd in pep8 pycodestyle pycodestyle-3
do
    which ${cmd} >/dev/null 2>&1
    if [[ $? -eq 0 ]]; then
        pep8_command=${cmd}
    fi
done

if [[ ${pep8_command} == "" ]]; then
    echo "No pep8 checker (pycodestyle, pep8) found."
    exit 99
fi

PEP8_TARGETS=${PEP8_TARGETS:-${DEFAULT_PEP8_TARGETS}}

PEP8_TARGET_PATHS=""
for target in ${PEP8_TARGETS}
do
    PEP8_TARGET_PATHS+=" ${top_srcdir}/${target}"
done

${pep8_command} --config ${top_srcdir}/tests/pep8/config ${PEP8_TARGET_PATHS}
