%post

restorecon -ir /etc/sysconfig/network-scripts /var/lib /etc/lvm \
               /dev /etc/iscsi /var/lib/iscsi /root /var/lock /var/log \
               /etc/modprobe.d /etc/sysconfig /var/cache/yum

restorecon -i /etc/rpm/macros /etc/dasd.conf /etc/zfcp.conf /lib64 /usr/lib64 \
              /etc/blkid.tab* /etc/mtab /etc/fstab /etc/resolv.conf \
              /etc/modprobe.conf* /var/log/*tmp /etc/crypttab \
              /etc/mdadm.conf /etc/sysconfig/network /root/install.log* \
              /etc/*shadow* /etc/dhcp/dhclient-*.conf /etc/localtime \
              /root/install.log*

if [ -e /etc/zipl.conf ]; then
    restorecon -i /etc/zipl.conf
fi

%end
