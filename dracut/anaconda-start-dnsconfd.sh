#!/bin/sh
# Attempt to start dnsconfd after boot options are parsed.
# The script needs to be run only after boot options are parsed,
# (parse-anaconda-* cmdline hooks are finished).
# There are also other attempts to start dnsconfd with start_dnsconfd
# called after parsing kickstart, see anaconda-lib.

. /lib/anaconda-lib.sh
start_dnsconfd "Anaconda boot options have been parsed"

