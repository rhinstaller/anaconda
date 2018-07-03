#!/bin/bash
# load modules needed by anaconda

# load anaconda-lib for the subsequent scripts in this hook
. /lib/anaconda-lib.sh

ARCH=$(uname -m)
KERNEL=$(uname -r)

MODULE_LIST="cramfs squashfs iscsi_tcp "

# if no file matches the glob expand it to the empty string
# we need this when any ko file cannot be found
shopt -s nullglob

DRIVERDIR=/lib/modules/$KERNEL/kernel/drivers
SCSI_MODULES=$DRIVERDIR/scsi/device_handler
NFIT_MODULE=$DRIVERDIR/acpi/nfit/nfit.ko
NVDIMM_MODULES=$DRIVERDIR/nvdimm
for m in $SCSI_MODULES/*.ko $NFIT_MODULE $NVDIMM_MODULES/*.ko ; do
    # Shell spew to work around not having basename
    # Trim the paths off the prefix, then the . suffix
    a="${m##*/}"
    MODULE_LIST+=" ${a%.*}"
done

shopt -u nullglob

if [ "$ARCH" != "s390" -a "$ARCH" != "s390x" ]; then
    MODULE_LIST+=" floppy edd iscsi_ibft "
else
    MODULE_LIST+=" hmcdrv "
fi

if [ "$ARCH" = "ppc" ]; then
    MODULE_LIST+=" spufs "
fi

MODULE_LIST+=" raid0 raid1 raid5 raid6 raid456 raid10 linear dm-mod dm-zero  \
              dm-mirror dm-snapshot dm-multipath dm-round-robin dm-crypt cbc \
              sha256 lrw xts "

for m in $MODULE_LIST; do
    if modprobe $m ; then
        debug_msg "$m was loaded"
    else
        debug_msg "$m was NOT loaded"
    fi
done
