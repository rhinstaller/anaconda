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

import os
import sys
from pyanaconda.constants import ROOT_PATH
from tempfile import mkstemp

from pyanaconda.bootloader import get_bootloader
from pyanaconda import constants
from pyanaconda import addons

import logging
log = logging.getLogger("anaconda")
stdoutLog = logging.getLogger("anaconda.stdout")

class Anaconda(object):
    def __init__(self):
        from pyanaconda import desktop

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
        self.opts = None
        self._payload = None
        self.proxy = None
        self.proxyUsername = None
        self.proxyPassword = None
        self.reIPLMessage = None
        self.rescue = False
        self.rescue_mount = True
        self.rootParts = None

        self.stage2 = None
        self._storage = None
        self.updateSrc = None
        self.mehConfig = None

        # *sigh* we still need to be able to write this out
        self.xdriver = None

    @property
    def bootloader(self):
        if not self._bootloader:
            self._bootloader = get_bootloader()

        return self._bootloader

    @property
    def instClass(self):
        if not self._instClass:
            from pyanaconda.installclass import DefaultInstall
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
    def payload(self):
        # Try to find the packaging payload class.  First try the install
        # class.  If it doesn't give us one, fall back to the default.
        if not self._payload:
            klass = self.instClass.getBackend()

            if not klass:
                from pyanaconda.flags import flags

                if flags.livecdInstall:
                    from pyanaconda.packaging.livepayload import LiveImagePayload
                    klass = LiveImagePayload
                elif self.ksdata.method.method == "liveimg":
                    from pyanaconda.packaging.livepayload import LiveImageKSPayload
                    klass = LiveImageKSPayload
                elif flags.dnf:
                    from pyanaconda.packaging.dnfpayload import DNFPayload as klass
                else:
                    from pyanaconda.packaging.yumpayload import YumPayload
                    klass = YumPayload

            self._payload = klass(self.ksdata)

        return self._payload

    @property
    def protected(self):
        import stat
        specs = []
        if os.path.exists("/run/initramfs/livedev") and \
           stat.S_ISBLK(os.stat("/run/initramfs/livedev")[stat.ST_MODE]):
            specs.append(os.readlink("/run/initramfs/livedev"))

        if self.methodstr and self.methodstr.startswith("hd:"):
            specs.append(self.methodstr[3:].split(":", 3)[0])

        if self.stage2 and self.stage2.startswith("hd:"):
            specs.append(self.stage2[3:].split(":", 3)[0])

        return specs

    @property
    def storage(self):
        if not self._storage:
            import blivet
            self._storage = blivet.Blivet(ksdata=self.ksdata)

            if self.instClass.defaultFS:
                self._storage.setDefaultFSType(self.instClass.defaultFS)

        return self._storage

    def dumpState(self):
        from meh import ExceptionInfo
        from meh.dump import ReverseExceptionDump
        from inspect import stack as _stack
        from traceback import format_stack

        # Skip the frames for dumpState and the signal handler.
        stack = _stack()[2:]
        stack.reverse()
        exn = ReverseExceptionDump(ExceptionInfo(None, None, stack),
                                   self.mehConfig)

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

    def initInterface(self, addon_paths=None):
        if self._intf:
            raise RuntimeError("Second attempt to initialize the InstallInterface")

        if self.displayMode == 'g':
            from pyanaconda.ui.gui import GraphicalUserInterface
            self._intf = GraphicalUserInterface(self.storage, self.payload,
                                                self.instClass)

            # needs to be refreshed now we know if gui or tui will take place
            addon_paths = addons.collect_addon_paths(constants.ADDON_PATHS,
                                                     ui_subdir="gui")
        elif self.displayMode in ['t', 'c']: # text and command line are the same
            from pyanaconda.ui.tui import TextUserInterface
            self._intf = TextUserInterface(self.storage, self.payload,
                                           self.instClass)

            # needs to be refreshed now we know if gui or tui will take place
            addon_paths = addons.collect_addon_paths(constants.ADDON_PATHS,
                                                     ui_subdir="tui")
        else:
            raise RuntimeError("Unsupported displayMode: %s" % self.displayMode)

        if addon_paths:
            self._intf.update_paths(addon_paths)

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
