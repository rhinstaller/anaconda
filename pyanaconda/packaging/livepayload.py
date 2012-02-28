#!/usr/bin/python

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
        # FIXME: this is broken. can't rsync from a device node to a directory.
        args = ["-rlptgoDHAXv", self.os_image, ROOT_PATH]
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
            if errorHandler(exn) == ERROR_RAISE:
                raise exn
