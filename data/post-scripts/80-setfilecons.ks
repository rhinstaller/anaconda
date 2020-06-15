%post
# We need to handle SELinux relabeling for a few reasons:
# - %post scripts that write files into places in /etc, but don't do
#   labeling correctly
# - Anaconda code that does the same (e.g. moving our log files into
#   /var/log/anaconda)
# - ostree payloads, where all of the labeling of /var is the installer's
#   responsibility (see https://github.com/ostreedev/ostree/pull/872 )
# - OSTree variants of the traditional mounts if present

restorecon -ir \
  /boot \
  /dev \
  /etc/*shadow* \
  /etc/X11/xorg.conf.d \
  /etc/blkid.tab* \
  /etc/crypttab \
  /etc/dasd.conf \
  /etc/dhcp/dhclient-*.conf \
  /etc/dnf/modules.d \
  /etc/fstab \
  /etc/group* \
  /etc/hostname \
  /etc/iscsi \
  /etc/localtime \
  /etc/lvm \
  /etc/mdadm.conf \
  /etc/modprobe.conf* \
  /etc/modprobe.d \
  /etc/mtab \
  /etc/passwd* \
  /etc/resolv.conf \
  /etc/rpm/macros \
  /etc/sysconfig \
  /etc/zfcp.conf \
  /etc/zipl.conf \
  /lib64 \
  /root \
  /usr/lib64 \
  /var/cache/yum \
  /var/home \
  /var/lib \
  /var/lock \
  /var/log \
  /var/media \
  /var/mnt \
  /var/opt \
  /var/roothome \
  /var/run \
  /var/spool \
  /var/srv \

%end
