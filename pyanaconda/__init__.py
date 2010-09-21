#!/usr/bin/python
#
# anaconda: The Red Hat Linux Installation program
#
# Copyright (C) 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007
# Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author(s): Brent Fox <bfox@redhat.com>
#            Mike Fulbright <msf@redhat.com>
#            Jakub Jelinek <jakub@redhat.com>
#            Jeremy Katz <katzj@redhat.com>
#            Chris Lumens <clumens@redhat.com>
#            Paul Nasrat <pnasrat@redhat.com>
#            Erik Troan <ewt@rpath.com>
#            Matt Wilson <msw@rpath.com>
#

import os, time, string
import iutil
import isys
from tempfile import mkstemp

import logging
log = logging.getLogger("anaconda")
stdoutLog = logging.getLogger("anaconda.stdout")

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class Anaconda(object):
    def __init__(self):
        import desktop, dispatch, firewall, security
        import system_config_keyboard.keyboard as keyboard
        from flags import flags

        self._backend = None
        self._bootloader = None
        self.canReIPL = False
        self.desktop = desktop.Desktop()
        self.dir = None
        self.dispatch = dispatch.Dispatcher(self)
        self.displayMode = None
        self.extraModules = []
        self.firewall = firewall.Firewall()
        self.id = None
        self._instClass = None
        self._instLanguage = None
        self._intf = None
        self.isHeadless = False
        self.keyboard = keyboard.Keyboard()
        self.ksdata = None
        self.mediaDevice = None
        self.methodstr = None
        self._network = None
        self.opts = None
        self._platform = None
        self.proxy = None
        self.proxyUsername = None
        self.proxyPassword = None
        self.reIPLMessage = None
        self.rescue = False
        self.rescue_mount = True
        self.rootParts = None
        self.rootPath = "/mnt/sysimage"
        self.security = security.Security()
        self.simpleFilter = not iutil.isS390()
        self.stage2 = None
        self._storage = None
        self._timezone = None
        self.updateSrc = None
        self.upgrade = flags.cmdline.has_key("preupgrade")
        self.upgradeRoot = None
        self.upgradeSwapInfo = None
        self._users = None
        self.mehConfig = None
        self.clearPartTypeSelection = None      # User's GUI selection
        self.clearPartTypeSystem = None         # System's selection

        # *sigh* we still need to be able to write this out
        self.xdriver = None

    @property
    def backend(self):
        if not self._backend:
            b = self.instClass.getBackend()
            self._backend = apply(b, (self, ))

        return self._backend

    @property
    def bootloader(self):
        if not self._bootloader:
            import booty
            self._bootloader = booty.getBootloader(self)

        return self._bootloader

    @property
    def firstboot(self):
        from pykickstart.constants import FIRSTBOOT_SKIP, FIRSTBOOT_DEFAULT

        if self.ksdata:
            return self.ksdata.firstboot.firstboot
        elif iutil.isS390():
            return FIRSTBOOT_SKIP
        else:
            return FIRSTBOOT_DEFAULT

    @property
    def instClass(self):
        if not self._instClass:
            from installclass import DefaultInstall
            self._instClass = DefaultInstall()

        return self._instClass

    @property
    def instLanguage(self):
        if not self._instLanguage:
            import language
            self._instLanguage = language.Language(self.displayMode)

        return self._instLanguage

    def _getInterface(self):
        return self._intf

    def _setInterface(self, v):
        # "lambda cannot contain assignment"
        self._intf = v

    def _delInterface(self):
        del self._intf

    intf = property(_getInterface, _setInterface, _delInterface)

    @property
    def network(self):
        if not self._network:
            import network
            self._network = network.Network()

        return self._network

    @property
    def platform(self):
        if not self._platform:
            from pyanaconda import platform
            self._platform = platform.getPlatform(self)

        return self._platform

    @property
    def protected(self):
        import stat

        if os.path.exists("/dev/live") and \
           stat.S_ISBLK(os.stat("/dev/live")[stat.ST_MODE]):
            return [os.readlink("/dev/live")]
        elif self.methodstr and self.methodstr.startswith("hd:"):
            method = self.methodstr[3:]
            return [method.split(":", 3)[0]]
        else:
            return []

    @property
    def users(self):
        if not self._users:
            import users
            self._users = users.Users(self)

        return self._users

    @property
    def storage(self):
        if not self._storage:
            import storage
            self._storage = storage.Storage(self)

        return self._storage

    @property
    def timezone(self):
        if not self._timezone:
            import timezone
            self._timezone = timezone.Timezone()
            self._timezone.setTimezoneInfo(self.instLanguage.getDefaultTimeZone(self.rootPath))

        return self._timezone

    def dumpState(self):
        from meh.dump import ReverseExceptionDump
        from inspect import stack as _stack

        # Skip the frames for dumpState and the signal handler.
        stack = _stack()[2:]
        stack.reverse()
        exn = ReverseExceptionDump((None, None, stack), self.mehConfig)

        # dump to a unique file
        (fd, filename) = mkstemp("", "anaconda-tb-", "/tmp")
        fo = os.fdopen(fd, "w")
        exn.write(self, fo)
        fo.close()

        #append to a given file
        with open(filename, "r") as f:
            content = f.readlines()
        with open("/tmp/anaconda-tb-all.log", "a+") as f:
            f.write("--- traceback: %s ---\n" % filename)
            f.writelines(content)

    def initInterface(self):
        if self._intf:
            raise RuntimeError, "Second attempt to initialize the InstallInterface"

        # setup links required by graphical mode if installing and verify display mode
        if self.displayMode == 'g':
            stdoutLog.info (_("Starting graphical installation."))

            try:
                from gui import InstallInterface
            except Exception, e:
                from flags import flags
                stdoutLog.error("Exception starting GUI installer: %s" %(e,))
                # if we're not going to really go into GUI mode, we need to get
                # back to vc1 where the text install is going to pop up.
                if not flags.livecdInstall:
                    isys.vtActivate (1)
                stdoutLog.warning("GUI installer startup failed, falling back to text mode.")
                self.displayMode = 't'
                if 'DISPLAY' in os.environ.keys():
                    del os.environ['DISPLAY']
                time.sleep(2)

        if self.displayMode == 't':
            from text import InstallInterface
            if not os.environ.has_key("LANG"):
                os.environ["LANG"] = "en_US.UTF-8"

        if self.displayMode == 'c':
            from cmdline import InstallInterface

        self._intf = InstallInterface()
        return self._intf

    def writeXdriver(self, root = None):
        # this should go away at some point, but until it does, we
        # need to keep it around.
        if self.xdriver is None:
            return
        if root is None:
            root = self.rootPath
        if not os.path.isdir("%s/etc/X11" %(root,)):
            os.makedirs("%s/etc/X11" %(root,), mode=0755)
        f = open("%s/etc/X11/xorg.conf" %(root,), 'w')
        f.write('Section "Device"\n\tIdentifier "Videocard0"\n\tDriver "%s"\nEndSection\n' % self.xdriver)
        f.close()

    def setMethodstr(self, methodstr):
        if methodstr.startswith("cdrom://"):
            (device, tree) = string.split(methodstr[8:], ":", 1)

            if not tree.startswith("/"):
                tree = "/%s" %(tree,)

            if device.startswith("/dev/"):
                device = device[5:]

            self.mediaDevice = device
            self.methodstr = "cdrom://%s" % tree
        else:
            self.methodstr = methodstr

    def requiresNetworkInstall(self):
        fail = False
        numNetDevs = isys.getNetworkDeviceCount()

        if self.methodstr is not None:
            if (self.methodstr.startswith("http") or \
                self.methodstr.startswith("ftp://") or \
                self.methodstr.startswith("nfs:")) and \
               numNetDevs == 0:
                fail = True
        elif self.stage2 is not None:
            if self.stage2.startswith("cdrom://") and \
               not os.path.isdir("/mnt/stage2/Packages") and \
               numNetDevs == 0:
                fail = True

        if fail:
            log.error("network install required, but no network devices available")

        return fail

    def write(self):
        self.writeXdriver()
        self.instLanguage.write(self.rootPath)

        self.timezone.write(self.rootPath)
        self.network.write()
        self.network.copyConfigToPath(instPath=self.rootPath)
        self.network.disableNMForStorageDevices(self,
                                                instPath=self.rootPath)
        self.desktop.write(self.rootPath)
        self.users.write(self.rootPath)
        self.security.write(self.rootPath)
        self.firewall.write(self.rootPath)

        services = list(self.storage.services)

        if self.ksdata:
            for svc in self.ksdata.services.disabled:
                iutil.execWithRedirect("/sbin/chkconfig",
                                       [svc, "off"],
                                       stdout="/dev/tty5", stderr="/dev/tty5",
                                       root=self.rootPath)

            services.extend(self.ksdata.services.enabled)

        for svc in services:
            iutil.execWithRedirect("/sbin/chkconfig",
                                   [svc, "on"],
                                   stdout="/dev/tty5", stderr="/dev/tty5",
                                   root=self.rootPath)

    def writeKS(self, filename):
        import urllib
        from pykickstart.version import versionToString, DEVEL

        f = open(filename, "w")

        f.write("# Kickstart file automatically generated by anaconda.\n\n")
        f.write("#version=%s\n" % versionToString(DEVEL))

        if self.upgrade:
            f.write("upgrade\n")
        else:
            f.write("install\n")

        m = None

        if self.methodstr:
            m = self.methodstr
        elif self.stage2:
            m = self.stage2

        if m:
            if m.startswith("cdrom:"):
                f.write("cdrom\n")
            elif m.startswith("hd:"):
                if m.count(":") == 3:
                    (part, fs, dir) = string.split(m[3:], ":")
                else:
                    (part, dir) = string.split(m[3:], ":")

                f.write("harddrive --partition=%s --dir=%s\n" % (part, dir))
            elif m.startswith("nfs:"):
                if m.count(":") == 3:
                    (opts, server, dir) = string.split(m[4:], ":")
                    f.write("nfs --server=%s --opts=%s --dir=%s\n" % (server, opts, dir))
                else:
                    (server, dir) = string.split(m[4:], ":")
                    f.write("nfs --server=%s --dir=%s\n" % (server, dir))
            elif m.startswith("ftp://") or m.startswith("http"):
                f.write("url --url=%s\n" % urllib.unquote(m))

        # Some kickstart commands do not correspond to any anaconda UI
        # component.  If this is a kickstart install, we need to make sure
        # the information from the input file ends up in the output file.
        if self.ksdata:
            f.write(self.ksdata.user.__str__())
            f.write(self.ksdata.services.__str__())
            f.write(self.ksdata.reboot.__str__())

        self.instLanguage.writeKS(f)

        if not self.isHeadless:
            self.keyboard.writeKS(f)
            self.network.writeKS(f)

        self.timezone.writeKS(f)
        self.users.writeKS(f)
        self.security.writeKS(f)
        self.firewall.writeKS(f)

        self.storage.writeKS(f)
        self.bootloader.writeKS(f)

        if self.backend:
            self.backend.writeKS(f)
            self.backend.writePackagesKS(f, self)

        # Also write out any scripts from the input ksfile.
        if self.ksdata:
            for s in self.ksdata.scripts:
                f.write(s.__str__())

        # make it so only root can read, could have password
        os.chmod(filename, 0600)
