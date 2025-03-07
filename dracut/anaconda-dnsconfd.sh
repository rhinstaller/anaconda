#!/bin/bash
# Enable dnsconfd.service in installer environment
# if dnsconfd backend is used.

dns_backend=$(getarg rd.net.dns-backend=)

if [ "${dns_backend}" == "dnsconfd" ]; then
    systemctl --root=/sysroot enable dnsconfd.service
    systemctl --root=/sysroot is-enabled systemd-resolved.service && systemctl --root=/sysroot disable systemd-resolved.service
fi
