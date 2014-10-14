%post

restorecon -ir /etc/sysconfig/network-scripts /var/lib /etc/lvm \
               /dev /etc/iscsi /var/lib/iscsi /root /var/lock /var/log \
               /etc/modprobe.d /etc/sysconfig /var/cache/yum

# Also relabel the OSTree variants of the normal mounts (if they exist)
restorecon -ir /var/roothome /var/home /var/opt /var/srv /var/media /var/mnt

restorecon -i /etc/rpm/macros /etc/dasd.conf /etc/zfcp.conf /lib64 /usr/lib64 \
              /etc/blkid.tab* /etc/mtab /etc/fstab /etc/resolv.conf \
              /etc/modprobe.conf* /var/log/*tmp /etc/crypttab \
              /etc/mdadm.conf /etc/sysconfig/network /root/install.log* \
              /etc/*shadow* /etc/dhcp/dhclient-*.conf /etc/localtime \
              /etc/hostname /root/install.log*

if [ -e /etc/zipl.conf ]; then
    restorecon -i /etc/zipl.conf
fi

%end
