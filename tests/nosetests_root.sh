#!/bin/sh

# Run only the nosetests that require root

srcdir=${srcdir:=$(dirname "$0")}
exec ${srcdir}/nosetests.sh ${srcdir}/nosetests/pyanaconda_tests/user_create_test.py \
                            ${srcdir}/nosetests/pyanaconda_tests/storage_test.py
