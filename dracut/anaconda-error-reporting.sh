#!/bin/bash
#
# Print what went wrong during the boot from installation perspective because Dracut seems
# to timeout soon!
#

warn "############# Anaconda installer errors begin #############"
warn "#                                                         #"
warn "It seems that the boot has failed. Possible causes include "
warn "missing inst.stage2 or inst.repo boot parameters on the "
warn "kernel cmdline. Please verify that you have specified "
warn "inst.stage2 or inst.repo."
warn "Please also note that the 'inst.' prefix is now mandatory."
warn "#                                                         #"
warn "####     Installer errors encountered during boot:     ####"
warn "#                                                         #"
if ! [ -e /run/anaconda/initrd_errors.txt ]; then
    warn "Reason unknown"
else
    while read -r line; do
        warn "$line"
    done < /run/anaconda/initrd_errors.txt
fi
warn "#                                                         #"
warn "############# Anaconda installer errors end ###############"

sleep 1
