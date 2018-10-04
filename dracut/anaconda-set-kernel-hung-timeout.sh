#!/bin/sh
# anaconda-set-kernel-hung-timeout.sh - set kernel hung timeout value
# Used for VM guests in kickstart tests (#1633549)

hung_timeout=$(getarg inst.kernel.hung_task_timeout_secs=)

if [ -n "$hung_timeout" ]; then
    echo ${hung_timeout} > /proc/sys/kernel/hung_task_timeout_secs
fi
