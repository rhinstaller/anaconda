#!/bin/bash

srcdir=${srcdir:=$(dirname "$0")}
COVERAGE_PROCESS_START=${COVERAGE_PROCESS_START:=${srcdir}/../.coveragerc}

if ! rpm -q python3-nose-testconfig &> /dev/null; then
    echo "python3-nose-testconfig is not available; exiting."
    exit 99
fi

export LC_ALL=C # translations confuse Dogtail

COVERAGE_PROCESS_START=${COVERAGE_PROCESS_START} exec \
    ${srcdir}/nosetests.sh -s --nologcapture --process-timeout 1200 \
    --tc=resultsdir:$(readlink -f autogui-results-$(date +"%Y%m%d_%H%M%S")) \
    ${srcdir}/gui/test_*.py
