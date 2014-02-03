#!/bin/bash
command -v getarg >/dev/null || . /lib/dracut-lib.sh

# initqueue/online hook passes interface name as $1
netif="$1"

# make sure we get ifcfg for every interface that comes up
save_netinfo $netif
