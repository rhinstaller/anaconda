#!/bin/bash
# parse-anaconda-cert.sh - handle inst.cert= boot option
#
# Supported formats:
#   inst.cert=cdrom:/path/to/cert.pem
#   inst.cert=hd:<dev>:/path/to/cert.pem
#
# The certificate must reside on the installation medium (CD/DVD or USB).
# The actual import happens in an initqueue job (anaconda-fetch-cert)
# triggered when the block device appears, which ensures the cert is
# trusted before any HTTPS network fetches take place.

command -v warn_critical >/dev/null || . /lib/anaconda-lib.sh

for cert_arg in $(getargs inst.cert=); do
    case "$cert_arg" in
        cdrom:*)
            cert_path="${cert_arg#cdrom:}"
            echo "$cert_path" >> /tmp/cert_cdrom
            info "anaconda: will import certificate $cert_path from cdrom"
            ;;
        hd:*)
            splitsep ":" "$cert_arg" _ diskdev cert_path
            echo "$diskdev $cert_path" >> /tmp/cert_disk
            info "anaconda: will import certificate $cert_path from $diskdev"
            ;;
        *)
            warn_critical "inst.cert: unsupported source '$cert_arg', use 'cdrom:' or 'hd:<dev>:'"
            ;;
    esac
done
