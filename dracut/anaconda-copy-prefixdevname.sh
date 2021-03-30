#!/bin/sh
# Copy over persistent network device names to anaconda environment

CMDLINE=$(cat /proc/cmdline)
if echo "${CMDLINE}" | grep -q "net.ifnames.prefix="; then
  mkdir -p /run/initramfs/state/etc/systemd/network
  cp /etc/systemd/network/*-net-ifnames-prefix* /run/initramfs/state/etc/systemd/network
fi
