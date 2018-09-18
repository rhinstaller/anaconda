#!/bin/sh
# Copy over persistent network device names to anaconda environment

CMDLINE=$(cat /proc/cmdline)
if [[ ${CMDLINE} =~ "net.ifnames.prefix=" ]]; then
  mkdir -p /run/initramfs/state/etc/systemd/network
  cp /etc/systemd/network/*-net-ifnames-prefix* /run/initramfs/state/etc/systemd/network
fi
