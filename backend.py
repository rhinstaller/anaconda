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

import logging
log = logging.getLogger("anaconda")

class ProxyBackend:
    def __init__(self, object=None):
        self.object = object

    def __getattr__(self, attr):
        if self.object:
            return getattr(self.object, attr)

class AnacondaBackend:
    def __init__(self, method):
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
        pass

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

