%post
# We need to handle SELinux relabeling for a few reasons:
# - %post scripts that write files into places in /etc, but don't do
#   labeling correctly
# - Anaconda code that does the same (e.g. moving our log files into
#   /var/log/anaconda)
# - ostree payloads, where all of the labeling of /var is the installer's
#   responsibility (see https://github.com/ostreedev/ostree/pull/872 )

restorecon -ir /etc/sysconfig/network-scripts /etc/lvm /etc/X11/xorg.conf.d \
               /etc/iscsi /etc/modprobe.d /etc/sysconfig \
               /var/lib /var/lib/iscsi /var/lock /var/log /var/spool \
               /var/cache/yum \
               /dev \
               /root

# Also relabel the OSTree variants of the traditional mounts if present
restorecon -ir /var/roothome /var/home /var/opt /var/srv /var/media /var/mnt

restorecon -i /etc/rpm/macros /etc/dasd.conf /etc/zfcp.conf /etc/blkid.tab* \
              /etc/mtab /etc/fstab /etc/resolv.conf /etc/modprobe.conf* \
              /etc/crypttab /etc/mdadm.conf /etc/sysconfig/network \
              /etc/*shadow* /etc/group* /etc/passwd* /etc/dhcp/dhclient-*.conf \
              /etc/localtime /etc/hostname /root/install.log* \
              /var/run /var/log/*tmp \
              /usr/lib64 \
              /lib64 \
              /root/install.log*

if [ -e /etc/zipl.conf ]; then
    restorecon -i /etc/zipl.conf
fi

%end
