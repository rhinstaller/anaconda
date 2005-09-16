#
# backend.py: Interface for installation backends
#
# Paul Nasrat <pnasrat@redhat.com> 
# Copyright (c) 2005 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import iutil
import os, sys
import logging
from syslogd import syslog

from rhpl.translate import _

from flags import flags
log = logging.getLogger("anaconda")


class AnacondaBackend:
    def __init__(self, method):
        """Abstract backend class all backends should inherit from this
           @param method: method uri string eg nfs://"""

        self.method = method
        self.instLog = None
        self.modeText = ""

    def doPreSelection(self, intf, id, instPath):
        pass

    def doPostSelection(self, intf, id, instPath):
        pass

    def doPreInstall(self, intf, id, instPath, dir):
        pass

    def doPostInstall(self, intf, id, instPath):
        sys.stdout.flush()
        if flags.setupFilesystems:
            syslog.stop()

    def doInstall(self, intf, id, instPath):
        pass

    def initLog(self, id, instPath):
        upgrade = id.getUpgrade()

        if upgrade:
            logname = '/root/upgrade.log'
        else:
            logname = '/root/install.log'

        instLogName = instPath + logname
        try:
            iutil.rmrf (instLogName)
        except OSError:
            pass

        instLog = open(instLogName, "w+")
        if upgrade:
            logname = '/root/upgrade.log'
        else:
            logname = '/root/install.log'

        instLogName = instPath + logname
        try:
            iutil.rmrf (instLogName)
        except OSError:
            pass

        self.instLog = open(instLogName, "w+")

       # dont start syslogd if we arent creating filesystems
        if flags.setupFilesystems:
            syslogname = "%s%s.syslog" % (instPath, logname)
            try:
                iutil.rmrf (syslogname)
            except OSError:
                pass
            syslog.start (instPath, syslogname)
        else:
            syslogname = None

        if upgrade:
            self.modeText = _("Upgrading %s-%s-%s.%s.\n")
        else:
            self.modeText = _("Installing %s-%s-%s.%s.\n")

    def kernelVersionList():
        pass


def doPreSelection(backend, intf, id, instPath):
    backend.doPreSelection(intf, id, instPath)

def doPostSelection(backend, intf, id, instPath):
    backend.doPostSelection(intf, id, instPath)

def doPreInstall(backend, intf, id, instPath, dir):
    backend.doPreInstall(intf, id, instPath, dir)

def doPostInstall(backend, intf, id, instPath):
    backend.doPostInstall(intf, id, instPath)

def doInstall(backend, intf, id, instPath):
    backend.doInstall(intf, id, instPath)

