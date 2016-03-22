#!/bin/sh

# Run only the nosetests that require root

srcdir=${srcdir:=$(dirname "$0")}
exec ${srcdir}/nosetests.sh ${srcdir}/pyanaconda_tests/user_create_test.py

if ! rpm -q python3-nose-testconfig &> /dev/null; then
    echo "python3-nose-testconfig is not available; exiting."
    exit 99
fi

export LC_ALL=C # translations confuse Dogtail

exec ${srcdir}/nosetests.sh -s --nologcapture --process-timeout 1200 \
    --tc=resultsdir:$(readlink -f autogui-results-$(date +"%Y%m%d_%H%M%S")) \
    ${srcdir}/gui/test_*.py
