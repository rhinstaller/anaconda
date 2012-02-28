#!/usr/bin/python

"""
    TODO
        - error handling!!!
        - document all methods

"""

import shutil

from . import *

try:
    import tarfile
except ImportError:
    log.error("import of tarfile failed")
    tarfile = None

from pyanaconda.constants import *
from pyanaconda.flags import flags

from pyanaconda import iutil

import logging
log = logging.getLogger("anaconda")

from pyanaconda.errors import *
#from pyanaconda.progress import progress

class TarPayload(ArchivePayload):
    """ A TarPayload unpacks a single tar archive onto the target system. """
    def __init__(self, data):
        if tarfile is None:
            raise PayloadError("unsupported payload type")

        super(TarPayload, self).__init__(data)
        self.archive = None

    def setup(self, storage):
        super(TarPayload, self).setup()

        try:
            self.archive = tarfile.open(self.image_file)
        except (tarfile.ReadError, tarfile.CompressionError) as e:
            # maybe we only need to catch ReadError and CompressionError here
            log.error("opening tar archive %s: %s" % (self.image_file, e))
            raise PayloadError("invalid payload format")

    @property
    def requiredSpace(self):
        byte_count = sum([m.size for m in self.archive.getmembers()])
        return byte_count / (1024.0 * 1024.0)   # FIXME: Size

    @property
    def kernelVersionList(self):
        names = self.archive.getnames()
        kernels = [n for n in names if "boot/vmlinuz-" in n]

    def install(self):
        try:
            self.archive.extractall(path=ROOT_PATH)
        except (tarfile.ExtractError, tarfile.CompressionError) as e:
            log.error("extracting tar archive %s: %s" % (self.image_file, e))

