#!/bin/bash
# This should start network-online.target which is wanted by anaconda
# based on its boot options. These options are parsed by parse-anaconda-*
# scripts and /tmp/net.iface file is updated accordingly. The file is
# the trigger used by anaconda to start in initramfs.
#
# We want to start the target because some services are wanted / triggered
# by the network-online.target, like dnsconfd.

if [ -f /tmp/net.ifaces ]; then
    systemctl start --no-block network-online.target
fi
