import unittest
import os
import subprocess


def makeLoopDev(device_name, file_name):
    proc = subprocess.Popen(["dd", "if=/dev/zero", "of=%s" % file_name,
                             "bs=1024", "count=102400"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    while True:
        (out, err) = proc.communicate()
        if proc.returncode is not None:
            rc = proc.returncode
            break
    if rc:
        raise OSError, "dd failed creating the file %s" % file_name

    proc = subprocess.Popen(["losetup", device_name, file_name],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    while True:
        (out, err) = proc.communicate()
        if proc.returncode is not None:
            rc = proc.returncode
            break
    if rc:
        raise OSError, "losetup failed setting up the loop device %s" % device_name

def removeLoopDev(device_name, file_name):
    proc = subprocess.Popen(["losetup", "-d", device_name],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    while True:
        (out, err) = proc.communicate()
        if proc.returncode is not None:
            rc = proc.returncode
            break
    if rc:
        raise OSError, "losetup failed removing the loop device %s" % device_name

    os.unlink(file_name)

def getFreeLoopDev():
    # There's a race condition here where another process could grab the loop
    # device losetup gives us before we have time to set it up, but that's just
    # a chance we'll have to take.
    proc = subprocess.Popen(["losetup", "-f"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out = None

    while True:
        (out, err) = proc.communicate()
        if proc.returncode is not None:
            rc = proc.returncode
            out = out.strip()
            break

    if rc:
        raise OSError, "losetup failed to find a free device"

    return out

class DevicelibsTestCase(unittest.TestCase):

    _LOOP_DEVICES = ["/tmp/test-virtdev0", "/tmp/test-virtdev1"]

    def __init__(self, *args, **kwargs):
        import pyanaconda.anaconda_log
        pyanaconda.anaconda_log.init()

        unittest.TestCase.__init__(self, *args, **kwargs)
        self._loopMap = {}

    def setUp(self):
        for file in self._LOOP_DEVICES:
            dev = getFreeLoopDev()
            makeLoopDev(dev, file)
            self._loopMap[file] = dev

    def tearDown(self):
        for (file, dev) in self._loopMap.iteritems():
            removeLoopDev(dev, file)
