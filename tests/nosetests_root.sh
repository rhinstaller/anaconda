#!/bin/sh

# Run only the nosetests that require root

srcdir=${srcdir:=$(dirname "$0")}
exec ${srcdir}/nosetests.sh ${srcdir}/pyanaconda_tests/user_create_test.py
