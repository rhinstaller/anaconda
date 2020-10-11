# Note, this script log will not be copied to the installed system.
%post --nochroot

NOSAVE_INPUT_KS_FILE=/tmp/NOSAVE_INPUT_KS
NOSAVE_LOGS_FILE=/tmp/NOSAVE_LOGS
PRE_ANA_LOGS=/tmp/pre-anaconda-logs
DNF_DEBUG_LOGS=/root/debugdata

if [ -e ${NOSAVE_LOGS_FILE} ]; then
    rm -f ${NOSAVE_LOGS_FILE}
else
    mkdir -p $ANA_INSTALL_PATH/var/log/anaconda
    for log in anaconda.log syslog X.log program.log packaging.log storage.log ifcfg.log lvm.log dnf.librepo.log hawkey.log dbus.log; do
        [ -e /tmp/$log ] && cp /tmp/$log $ANA_INSTALL_PATH/var/log/anaconda/
    done
    [ -e /tmp/pre-anaconda-logs ] && cp -r $PRE_ANA_LOGS $ANA_INSTALL_PATH/var/log/anaconda
    # copy DNF debug data (if any)
    [ -e $DNF_DEBUG_LOGS ] && cp -r $DNF_DEBUG_LOGS $ANA_INSTALL_PATH/var/log/anaconda/dnf_debugdata
    cp /tmp/ks-script*.log $ANA_INSTALL_PATH/var/log/anaconda/
    journalctl -b > $ANA_INSTALL_PATH/var/log/anaconda/journal.log
    chmod 0600 $ANA_INSTALL_PATH/var/log/anaconda/*
fi

if [ -e ${NOSAVE_INPUT_KS_FILE} ]; then
    rm -f ${NOSAVE_INPUT_KS_FILE}
elif [ -e /run/install/ks.cfg ]; then
    cp /run/install/ks.cfg $ANA_INSTALL_PATH/root/original-ks.cfg
fi

%end

%post
# Relabel the anaconda logs we've just coppied, since they could be incorrectly labeled, like
# hawkey.log: https://bugzilla.redhat.com/show_bug.cgi?id=1885772.
# Execution of this %post script will not be logged in the log files on the installed system.

restorecon -ir /var/log/anaconda/

%end
