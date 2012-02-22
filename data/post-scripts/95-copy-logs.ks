%post --nochroot

mkdir -p /mnt/sysimage/var/log/anaconda
[ -e /tmp/anaconda.log ] && cp /tmp/anaconda.log /mnt/sysimage/var/log/anaconda/anaconda.log
[ -e /tmp/syslog ] && cp /tmp/syslog /mnt/sysimage/var/log/anaconda/syslog
[ -e /tmp/X.log ] && cp /tmp/X.log /mnt/sysimage/var/log/anaconda.anaconda.xlog
[ -e /tmp/program.log ] && cp /tmp/program.log /mnt/sysimage/var/log/anaconda/anaconda.program.log
[ -e /tmp/storage.log ] && cp /tmp/storage.log /mnt/sysimage/var/log/anaconda/anaconda.storage.log
[ -e /tmp/ifcfg.log ] && cp /tmp/ifcfg.log /mnt/sysimage/var/log/anaconda/anaconda.ifcfg.log
[ -e /tmp/yum.log ] && cp /tmp/yum.log /mnt/sysimage/var/log/anaconda/anaconda.yum.log
chmod 0600 /mnt/sysimage/var/log/anaconda/*

%end
