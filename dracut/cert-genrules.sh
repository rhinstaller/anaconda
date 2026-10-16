#!/bin/sh
# cert-genrules.sh - generate udev rules to import inst.cert= certificates
#
# Triggers anaconda-fetch-cert when the certificate source device appears,
# ensuring certificates are trusted before any HTTPS network fetches.

. /lib/anaconda-lib.sh

# Job name "01-anaconda-cert" ensures cert import runs before stage2/kickstart
# HTTPS fetches: "01-anaconda-cert<PID>.sh" sorts before "99-nm-run.sh".

# cdrom: - trigger on any CD/DVD device with media
if [ -f /tmp/cert_cdrom ]; then
    when_any_cdrom_appears 01-anaconda-cert \
        anaconda-fetch-cert "\$env{DEVNAME}"
fi

# hd: - trigger on the specific disk device
if [ -f /tmp/cert_disk ]; then
    while IFS=' ' read -r diskdev cert_path; do
        diskdev=$(disk_to_dev_path "$diskdev")
        when_diskdev_appears "$diskdev" 01-anaconda-cert \
            anaconda-fetch-cert "\$env{DEVNAME}" "$cert_path"
    done < /tmp/cert_disk
fi
