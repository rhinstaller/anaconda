import unittest
import os
import subprocess

# need to import these first before doing anything
import anaconda_log
import upgrade

class TestDevicelibs(unittest.TestCase):

    _LOOP_DEVICES = (("/dev/loop0", "/tmp/test-virtdev0"),
                     ("/dev/loop1", "/tmp/test-virtdev1"))

    ((_LOOP_DEV0, _LOOP_FILE0), (_LOOP_DEV1, _LOOP_FILE1)) = _LOOP_DEVICES

    def setUp(self):
        for dev, file in self._LOOP_DEVICES:
            self.makeLoopDev(dev, file)

    def tearDown(self):
        for dev, file in self._LOOP_DEVICES:
            self.removeLoopDev(dev, file)

    def makeLoopDev(self, device_name, file_name):
        proc = subprocess.Popen(["dd", "if=/dev/zero", "of=%s" % file_name, "bs=1024", "count=102400"])
        while True:
            proc.communicate()
            if proc.returncode is not None:
                rc = proc.returncode
                break
        if rc:
            raise OSError, "dd failed creating the file %s" % file_name

        proc = subprocess.Popen(["losetup", device_name, file_name])
        while True:
            proc.communicate()
            if proc.returncode is not None:
                rc = proc.returncode
                break
        if rc:
            raise OSError, "losetup failed setting up the loop device %s" % device_name

    def removeLoopDev(self, device_name, file_name):
        proc = subprocess.Popen(["losetup", "-d", device_name])
        while True:
            proc.communicate()
            if proc.returncode is not None:
                rc = proc.returncode
                break
        if rc:
            raise OSError, "losetup failed removing the loop device %s" % device_name

        os.remove(file_name)
