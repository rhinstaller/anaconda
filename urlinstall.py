#
# urlinstall.py - URL based install source method
#
# Erik Troan <ewt@redhat.com>
#
# Copyright 1999-2007 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

from installmethod import InstallMethod
import os
import time
import shutil
import string
import socket
import urlparse
import urlgrabber.grabber as grabber
import isys

from snack import *
from constants import *

from rhpl.translate import _

import logging
log = logging.getLogger("anaconda")

class UrlInstallMethod(InstallMethod):

    def systemMounted(self, fsset, chroot):
        if self.tree is None:
            return
        if not os.path.exists("%s/images/stage2.img" %(self.tree,)):
            log.debug("Not copying stage2.img as we can't find it")
            return

        self.loopbackFile = "%s%s%s" % (chroot,
                                        fsset.filesystemSpace(chroot)[0][0],
                                        "/rhinstall-stage2.img")

        try:
            win = self.waitWindow (_("Copying File"),
                                   _("Transferring install image to hard drive..."))
            shutil.copyfile("%s/images/stage2.img" % (self.tree,), 
                            self.loopbackFile)
            win.pop()
        except Exception, e:
            if win:
                win.pop()

            log.critical("error transferring stage2.img: %s" %(e,))
            self.messageWindow(_("Error"),
                    _("An error occurred transferring the install image "
                      "to your hard drive. You are probably out of disk "
                      "space."))
            os.unlink(self.loopbackFile)
            return 1

        isys.lochangefd("/dev/loop0", self.loopbackFile)

    def getMethodUri(self):
        return self.baseUrl

    def unmountCD(self):
        if not self.tree:
            return

        done = 0
        while done == 0:
            try:
                isys.umount("/mnt/source")
                break
            except Exception, e:
                log.error("exception in unmountCD: %s" %(e,))
                self.messageWindow(_("Error"),
                                   _("An error occurred unmounting the disc.  "
                                     "Please make sure you're not accessing "
                                     "%s from the shell on tty2 "
                                     "and then click OK to retry.")
                                   % ("/mnt/source",))

    def filesDone(self):
        # we're trying to unmount the CD here.  if it fails, oh well,
        # they'll reboot soon enough I guess :)
        try:
            isys.umount("/mnt/source")
        except Exception:
            pass

        if not self.loopbackFile: return

        try:
            # this isn't the exact right place, but it's close enough
            os.unlink(self.loopbackFile)
        except SystemError:
            pass

    def __init__(self, url, rootPath, intf):
	InstallMethod.__init__(self, url, rootPath, intf)

        (scheme, netloc, path, query, fragid) = urlparse.urlsplit(url)

	try:
            socket.inet_pton(socket.AF_INET6, netloc)
            netloc = '[' + netloc + ']'
        except:
            pass

        # encoding fun so that we can handle absolute paths
        if scheme == "ftp" and path and path.startswith("//"):
            path = "/%2F" + path[1:]

        self.baseUrl = urlparse.urlunsplit((scheme,netloc,path,query,fragid))
        self.pkgUrl = self.baseUrl

        self.currentMedia = []

        self.messageWindow = intf.messageWindow
        self.progressWindow = intf.progressWindow
        self.waitWindow = intf.waitWindow
        self.loopbackFile = None
        self.tree = "/mnt/source"
        for path in ("/tmp/ramfs/stage2.img", "/tmp/ramfs/minstg2.img"):
            if os.access(path, os.R_OK):
                # we used a remote stage2. no need to worry about ejecting CDs
                self.tree = None
                break
