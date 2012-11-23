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
import sys
import iutil
import isys
from constants import ROOT_PATH
from tempfile import mkstemp

import logging
log = logging.getLogger("anaconda")
stdoutLog = logging.getLogger("anaconda.stdout")

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class Anaconda(object):
    def __init__(self):
        import desktop
        from flags import flags

        self._backend = None
        self._bootloader = None
        self.canReIPL = False
        self.desktop = desktop.Desktop()
        self.dir = None
        self.displayMode = None
        self.extraModules = []
        self.id = None
        self._instClass = None
        self._intf = None
        self.isHeadless = False
        self.ksdata = None
        self.mediaDevice = None
        self.methodstr = None
        self._network = None
        self.opts = None
        self._payload = None
        self._platform = None
        self.proxy = None
        self.proxyUsername = None
        self.proxyPassword = None
        self.reIPLMessage = None
        self.rescue = False
        self.rescue_mount = True
        self.rootParts = None
        self.simpleFilter = not iutil.isS390()
        self.stage2 = None
        self._storage = None
        self.updateSrc = None
        self.upgrade = flags.cmdline.has_key("preupgrade")
        self.upgradeRoot = None
        self.mehConfig = None

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
            self._bootloader = self.platform.bootloaderClass(self.platform)

        return self._bootloader

    @property
    def instClass(self):
        if not self._instClass:
            from installclass import DefaultInstall
            self._instClass = DefaultInstall()

        return self._instClass

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
    def payload(self):
        # Try to find the packaging payload class.  First try the install
        # class.  If it doesn't give us one, fall back to the default.
        if not self._payload:
            klass = self.instClass.getBackend()

            if not klass:
                from flags import flags

                if flags.livecdInstall:
                    from pyanaconda.packaging.livepayload import LiveImagePayload
                    klass = LiveImagePayload
                else:
                    from pyanaconda.packaging.yumpayload import YumPayload
                    klass = YumPayload

            self._payload = klass(self.ksdata)

        return self._payload

    @property
    def platform(self):
        if not self._platform:
            from pyanaconda import platform
            self._platform = platform.getPlatform()

        return self._platform

    @property
    def protected(self):
        import stat

        if os.path.exists("/run/initramfs/livedev") and \
           stat.S_ISBLK(os.stat("/run/initramfs/livedev")[stat.ST_MODE]):
            return [os.readlink("/run/initramfs/livedev")]
        elif self.methodstr and self.methodstr.startswith("hd:"):
            method = self.methodstr[3:]
            return [method.split(":", 3)[0]]
        else:
            return []

    @property
    def storage(self):
        if not self._storage:
            import storage
            self._storage = storage.Storage(data=self.ksdata, platform=self.platform)

        return self._storage

    def dumpState(self):
        from meh.dump import ReverseExceptionDump
        from inspect import stack as _stack
        from traceback import format_stack

        # Skip the frames for dumpState and the signal handler.
        stack = _stack()[2:]
        stack.reverse()
        exn = ReverseExceptionDump((None, None, stack), self.mehConfig)

        # gather up info on the running threads
        threads = "\nThreads\n-------\n"
        for thread_id, frame in sys._current_frames().iteritems():
            threads += "\nThread %s\n" % (thread_id,)
            threads += "".join(format_stack(frame))

        # dump to a unique file
        (fd, filename) = mkstemp(prefix="anaconda-tb-", dir="/tmp")
        dump_text = exn.traceback_and_object_dump(self)
        dump_text += threads
        dump_text = dump_text.encode("utf-8")
        os.write(fd, dump_text)
        os.close(fd)

        # append to a given file
        with open("/tmp/anaconda-tb-all.log", "a+") as f:
            f.write("--- traceback: %s ---\n" % filename)
            f.write(dump_text + "\n")

    def initInterface(self):
        if self._intf:
            raise RuntimeError, "Second attempt to initialize the InstallInterface"

        if self.displayMode == 'g':
            from pyanaconda.ui.gui import GraphicalUserInterface
            self._intf = GraphicalUserInterface(self.storage, self.payload,
                                                self.instClass)
        elif self.displayMode in ['t', 'c']: # text and command line are the same
            from pyanaconda.ui.tui import TextUserInterface
            self._intf = TextUserInterface(self.storage, self.payload,
                                           self.instClass)
        else:
            raise RuntimeError("Unsupported displayMode: %s" % self.displayMode)

    def writeXdriver(self, root = None):
        # this should go away at some point, but until it does, we
        # need to keep it around.
        if self.xdriver is None:
            return
        if root is None:
            root = ROOT_PATH
        if not os.path.isdir("%s/etc/X11" %(root,)):
            os.makedirs("%s/etc/X11" %(root,), mode=0755)
        f = open("%s/etc/X11/xorg.conf" %(root,), 'w')
        f.write('Section "Device"\n\tIdentifier "Videocard0"\n\tDriver "%s"\nEndSection\n' % self.xdriver)
        f.close()

    def write(self):
        import network
        self.writeXdriver()

        network.write_sysconfig_network()
        network.disableIPV6()
        network.copyConfigToPath(ROOT_PATH)
        if not self.ksdata:
            self.instClass.setNetworkOnbootDefault()
        self.desktop.write()
