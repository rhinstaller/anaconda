import unittest
import os
import subprocess

class TestDevicelibs(unittest.TestCase):

    _LOOP_DEVICES = (("/dev/loop0", "/tmp/test-virtdev0"),
                     ("/dev/loop1", "/tmp/test-virtdev1"))

    ((_LOOP_DEV0, _LOOP_FILE0), (_LOOP_DEV1, _LOOP_FILE1)) = _LOOP_DEVICES

    def setUp(self):
        for dev, file in self._LOOP_DEVICES:
            proc = subprocess.Popen(["dd", "if=/dev/zero", "of=%s" % file, "bs=1024", "count=102400"])
            while True:
                proc.communicate()
                if proc.returncode is not None:
                    rc = proc.returncode
                    break
            if rc:
                raise OSError, "dd failed creating the file %s" % file
            
            proc = subprocess.Popen(["losetup", dev, file])
            while True:
                proc.communicate()
                if proc.returncode is not None:
                    rc = proc.returncode
                    break
            if rc:
                raise OSError, "losetup failed setting up the loop device %s" % dev

    def tearDown(self):
        for dev, file in self._LOOP_DEVICES:
            proc = subprocess.Popen(["losetup", "-d", dev])
            while True:
                proc.communicate()
                if proc.returncode is not None:
                    rc = proc.returncode
                    break
            if rc:
                raise OSError, "losetup failed removing the loop device %s" % dev

            os.remove(file)
