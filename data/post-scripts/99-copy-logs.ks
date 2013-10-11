# Note, this script log will not be copied to the installed system.
%post --nochroot

mkdir -p /mnt/sysimage/var/log/anaconda
[ -e /tmp/anaconda.log ] && cp /tmp/anaconda.log $ANA_INSTALL_PATH/var/log/anaconda/anaconda.log
[ -e /tmp/syslog ] && cp /tmp/syslog $ANA_INSTALL_PATH/var/log/anaconda/syslog
[ -e /tmp/X.log ] && cp /tmp/X.log $ANA_INSTALL_PATH/var/log/anaconda/anaconda.xlog
[ -e /tmp/program.log ] && cp /tmp/program.log $ANA_INSTALL_PATH/var/log/anaconda/anaconda.program.log
[ -e /tmp/packaging.log ] && cp /tmp/packaging.log $ANA_INSTALL_PATH/var/log/anaconda/anaconda.packaging.log
[ -e /tmp/storage.log ] && cp /tmp/storage.log $ANA_INSTALL_PATH/var/log/anaconda/anaconda.storage.log
[ -e /tmp/ifcfg.log ] && cp /tmp/ifcfg.log $ANA_INSTALL_PATH/var/log/anaconda/anaconda.ifcfg.log
[ -e /tmp/yum.log ] && cp /tmp/yum.log $ANA_INSTALL_PATH/var/log/anaconda/anaconda.yum.log
cp /tmp/ks-script*.log $ANA_INSTALL_PATH/var/log/anaconda/
journalctl -b > $ANA_INSTALL_PATH/var/log/anaconda/anaconda.journal.log
chmod 0600 /mnt/sysimage/var/log/anaconda/*

%end
