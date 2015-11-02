# Note, this script log will not be copied to the installed system.
%post --nochroot

mkdir -p $ANA_INSTALL_PATH/var/log/anaconda
for log in anaconda.log syslog X.log program.log packaging.log storage.log ifcfg.log yum.log; do
    [ -e /tmp/$log ] && cp /tmp/$log $ANA_INSTALL_PATH/var/log/anaconda/
done
cp /tmp/ks-script*.log $ANA_INSTALL_PATH/var/log/anaconda/
journalctl -b > $ANA_INSTALL_PATH/var/log/anaconda/journal.log
chmod 0600 $ANA_INSTALL_PATH/var/log/anaconda/*

# Copy over any rhsm logs
[ -e /var/log/rhsm/ ] && cp -r /var/log/rhsm $ANA_INSTALL_PATH/var/log/

%end
