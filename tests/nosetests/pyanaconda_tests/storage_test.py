import os
import unittest
from unittest.mock import patch

from blivet import util
from blivet.size import Size

from pyanaconda.storage.osinstall import InstallerStorage, storage_initialize
try:
    from pyanaconda import kickstart
    pyanaconda_present = True
except ImportError:
    pyanaconda_present = False


@unittest.skip("not working")
@unittest.skipUnless(os.geteuid() == 0, "requires root privileges")
class setupDiskImagesNonZeroSizeTestCase(unittest.TestCase):
    """
        Test if size of disk images is > 0. Related: rhbz#1252703.
        This test emulates how anaconda configures its storage.
    """

    disks = {"disk1": Size("2 GiB")}

    def setUp(self):
        self.storage = InstallerStorage()

        # anaconda first configures disk images
        for (name, size) in iter(self.disks.items()):
            path = util.create_sparse_tempfile(name, size)
            self.storage.disk_images[name] = path

        # at this point the DMLinearDevice has correct size
        self.storage.setup_disk_images()

        # no kickstart available
        ksdata = kickstart.AnacondaKSHandler([])
        # anaconda calls storage_initialize regardless of whether or not
        # this is an image install. Somewhere along the line this will
        # execute setup_disk_images() once more and the DMLinearDevice created
        # in this second execution has size 0
        with patch('blivet.flags'):
            storage_initialize(self.storage, ksdata, [])

    def tearDown(self):
        self.storage.reset()
        self.storage.devicetree.teardown_disk_images()
        for fn in self.storage.disk_images.values():
            if os.path.exists(fn):
                os.unlink(fn)

    def runTest(self):
        disk = self.storage.disks[0]
        self.assertEqual(disk.name, list(self.disks.keys())[0])
        for d in self.storage.devicetree.devices:
            if d == disk or disk.depends_on(d):
                self.assertTrue(d.size > 0)


if __name__ == "__main__":
    unittest.main()
