# livepayload.py
# Live media software payload management.
#
# Copyright (C) 2012  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): David Lehman <dlehman@redhat.com>
#

"""
    TODO
        - error handling!!!
        - document all methods
        - LiveImagePayload
            - register the live image, either via self.data.method or in setup
              using storage

"""
import os
import stat

from . import *

from pyanaconda.constants import *
from pyanaconda.flags import flags

from pyanaconda import iutil

import logging
log = logging.getLogger("anaconda")

from pyanaconda.errors import *
#from pyanaconda.progress import progress

class LiveImagePayload(ImagePayload):
    """ A LivePayload copies the source image onto the target system. """
    def setup(self, storage):
        super(LiveImagePayload, self).setup()
        if not stat.S_ISBLK(os.stat(self.image_file)[stat.ST_MODE]):
            raise PayloadSetupError("unable to find image")

    def install(self):
        """ Install the payload. """
        cmd = "rsync"
        args = ["-rlptgoDHAXvx", "/", ROOT_PATH]
        try:
            rc = iutil.execWithRedirect(cmd, args,
                                        stderr="/dev/tty5", stdout="/dev/tty5")
        except (OSError, RuntimeError) as e:
            err = str(e)
        else:
            err = None
            if rc != 0:
                err = "%s exited with code %d" % (cmd, rc)

        if err:
            exn = PayloadInstallError(err)
            if errorHandler.cb(exn) == ERROR_RAISE:
                raise exn
