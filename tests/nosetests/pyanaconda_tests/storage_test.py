import os
import unittest
from unittest.mock import patch

from blivet import util
from blivet.size import Size

from pyanaconda.modules.storage.devicetree import create_storage
from pyanaconda.ui.lib.storage import reset_storage


@unittest.skip("not working")
@unittest.skipUnless(os.geteuid() == 0, "requires root privileges")
class SetupDiskImagesNonZeroSizeTestCase(unittest.TestCase):
    """
        Test if size of disk images is > 0. Related: rhbz#1252703.
        This test emulates how anaconda configures its storage.
    """

    disks = {"disk1": Size("2 GiB")}

    def setUp(self):
        self.storage = create_storage()

        # anaconda first configures disk images
        for (name, size) in iter(self.disks.items()):
            path = util.create_sparse_tempfile(name, size)
            self.storage.disk_images[name] = path

        # at this point the DMLinearDevice has correct size
        self.storage.setup_disk_images()

        # anaconda calls initialize_storage regardless of whether or not
        # this is an image install. Somewhere along the line this will
        # execute setup_disk_images() once more and the DMLinearDevice created
        # in this second execution has size 0
        with patch('blivet.flags'):
            reset_storage()

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
