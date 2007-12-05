#
# installmethod.py - Base class for install methods
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

import os, shutil, string
from constants import *

import logging
log = logging.getLogger("anaconda")

import isys, product

def doMethodComplete(anaconda):
    try:
        isys.umount(anaconda.backend.ayum.tree)
    except Exception:
        pass

    if anaconda.methodstr.startswith("cdrom://"):
        try:
            shutil.copyfile("%s/media.repo" % anaconda.backend.ayum.tree,
                            "%s/etc/yum.repos.d/%s-install-media.repo" %(anaconda.rootPath, productName))
        except Exception, e:
            log.debug("Error copying media.repo: %s" %(e,))

    if anaconda.backend.ayum._loopbackFile:
        try:
            os.unlink(anaconda.backend.ayum._loopbackFile)
        except SystemError:
            pass

    if not anaconda.isKickstart and anaconda.mediaDevice:
        isys.ejectCdrom(anaconda.mediaDevice, makeDevice=1)

    mtab = "/dev/root / ext3 ro 0 0\n"
    for ent in anaconda.id.fsset.entries:
        if ent.mountpoint == "/":
            mtab = "/dev/root / %s ro 0 0\n" %(ent.fsystem.name,)

    f = open(anaconda.rootPath + "/etc/mtab", "w+")
    f.write(mtab)
    f.close()
