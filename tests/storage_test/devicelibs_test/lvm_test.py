#!/usr/bin/python
import baseclass
import unittest
from mock import acceptance

class LVMTestCase(baseclass.DevicelibsTestCase):

    def testLVM(self):
        _LOOP_DEV0 = self._loopMap[self._LOOP_DEVICES[0]]
        _LOOP_DEV1 = self._loopMap[self._LOOP_DEVICES[1]]

        import storage.devicelibs.lvm as lvm


    @acceptance
    def testLVM(self):
        ##
        ## pvcreate
        ##
        # pass
        for dev, file in self._loopMap.iteritems():
            self.assertEqual(lvm.pvcreate(dev), None)

        # fail
        self.assertRaises(lvm.LVMError, lvm.pvcreate, "/not/existing/device")

        ##
        ## pvresize
        ##
        # pass
        for dev, file in self._loopMap.iteritems():
            self.assertEqual(lvm.pvresize(dev, 50), None)
            self.assertEqual(lvm.pvresize(dev, 100), None)

        # fail
        self.assertRaises(lvm.LVMError, lvm.pvresize, "/not/existing/device", 50)

        ##
        ## vgcreate
        ##
        # pass
        self.assertEqual(lvm.vgcreate("test-vg", [_LOOP_DEV0, _LOOP_DEV1], 4), None)

        # fail
        self.assertRaises(lvm.LVMError, lvm.vgcreate, "another-vg", ["/not/existing/device"], 4)
        # vg already exists
        self.assertRaises(lvm.LVMError, lvm.vgcreate, "test-vg", [_LOOP_DEV0], 4)
        # pe size must be power of 2
        self.assertRaises(lvm.LVMError, lvm.vgcreate, "another-vg", [_LOOP_DEV0], 5)

        ##
        ## pvremove
        ##
        # fail
        # cannot remove pv now with vg created
        self.assertRaises(lvm.LVMError, lvm.pvremove, _LOOP_DEV0)

        ##
        ## vgdeactivate
        ##
        # pass
        self.assertEqual(lvm.vgdeactivate("test-vg"), None)
        
        # fail
        self.assertRaises(lvm.LVMError, lvm.vgdeactivate, "wrong-vg-name")
        
        ##
        ## vgreduce
        ##
        # pass
        self.assertEqual(lvm.vgreduce("test-vg", [_LOOP_DEV1]), None)

        # fail
        self.assertRaises(lvm.LVMError, lvm.vgreduce, "wrong-vg-name", [_LOOP_DEV1])
        self.assertRaises(lvm.LVMError, lvm.vgreduce, "test-vg", ["/not/existing/device"])

        ##
        ## vgactivate
        ##
        # pass
        self.assertEqual(lvm.vgactivate("test-vg"), None)

        # fail
        self.assertRaises(lvm.LVMError, lvm.vgactivate, "wrong-vg-name")
        
        ##
        ## pvinfo
        ##
        # pass
        self.assertEqual(lvm.pvinfo(_LOOP_DEV0)["pv_name"], _LOOP_DEV0)
        # no vg
        self.assertEqual(lvm.pvinfo(_LOOP_DEV1)["pv_name"], _LOOP_DEV1)

        # fail
        self.assertRaises(lvm.LVMError, lvm.pvinfo, "/not/existing/device")

        ##
        ## vginfo
        ##
        # pass
        self.assertEqual(lvm.vginfo("test-vg")["pe_size"], "4.00")

        # fail
        self.assertRaises(lvm.LVMError, lvm.vginfo, "wrong-vg-name")

        ##
        ## lvcreate
        ##
        # pass
        self.assertEqual(lvm.lvcreate("test-vg", "test-lv", 10), None)

        # fail
        self.assertRaises(lvm.LVMError, lvm.lvcreate, "wrong-vg-name", "another-lv", 10)

        ##
        ## lvdeactivate
        ##
        # pass
        self.assertEqual(lvm.lvdeactivate("test-vg", "test-lv"), None)

        # fail
        self.assertRaises(lvm.LVMError, lvm.lvdeactivate, "test-vg", "wrong-lv-name")
        self.assertRaises(lvm.LVMError, lvm.lvdeactivate, "wrong-vg-name", "test-lv")
        self.assertRaises(lvm.LVMError, lvm.lvdeactivate, "wrong-vg-name", "wrong-lv-name")

        ##
        ## lvresize
        ##
        # pass
        self.assertEqual(lvm.lvresize("test-vg", "test-lv", 60), None)

        # fail
        self.assertRaises(lvm.LVMError, lvm.lvresize, "test-vg", "wrong-lv-name", 80)
        self.assertRaises(lvm.LVMError, lvm.lvresize, "wrong-vg-name", "test-lv", 80)
        self.assertRaises(lvm.LVMError, lvm.lvresize, "wrong-vg-name", "wrong-lv-name", 80)
        # changing to same size
        self.assertRaises(lvm.LVMError, lvm.lvresize, "test-vg", "test-lv", 60)

        ##
        ## lvactivate
        ##
        # pass
        self.assertEqual(lvm.lvactivate("test-vg", "test-lv"), None)

        # fail
        self.assertRaises(lvm.LVMError, lvm.lvactivate, "test-vg", "wrong-lv-name")
        self.assertRaises(lvm.LVMError, lvm.lvactivate, "wrong-vg-name", "test-lv")
        self.assertRaises(lvm.LVMError, lvm.lvactivate, "wrong-vg-name", "wrong-lv-name")

        ##
        ## lvs
        ##
        # pass
        self.assertEqual(lvm.lvs("test-vg")["test-lv"]["size"], "60.00")

        # fail
        self.assertRaises(lvm.LVMError, lvm.lvs, "wrong-vg-name")

        ##
        ## has_lvm
        ##
        # pass
        self.assertEqual(lvm.has_lvm(), True)

        # fail
        # TODO

        ##
        ## lvremove
        ##
        # pass
        self.assertEqual(lvm.lvdeactivate("test-vg", "test-lv"), None)      # is deactivation needed?
        self.assertEqual(lvm.lvremove("test-vg", "test-lv"), None)

        # fail
        self.assertRaises(lvm.LVMError, lvm.lvremove, "test-vg", "wrong-lv-name")
        self.assertRaises(lvm.LVMError, lvm.lvremove, "wrong-vg-name", "test-lv")
        self.assertRaises(lvm.LVMError, lvm.lvremove, "wrong-vg-name", "wrong-lv-name")
        # lv already removed
        self.assertRaises(lvm.LVMError, lvm.lvremove, "test-vg", "test-lv")

        ##
        ## vgremove
        ##
        # pass
        self.assertEqual(lvm.vgremove("test-vg"), None)

        # fail
        self.assertRaises(lvm.LVMError, lvm.vgremove, "wrong-vg-name")
        # vg already removed
        self.assertRaises(lvm.LVMError, lvm.vgremove, "test-vg")

        ##
        ## pvremove
        ##
        # pass
        for dev, file in self._loopMap.iteritems():
            self.assertEqual(lvm.pvremove(dev), None)

        # fail
        self.assertRaises(lvm.LVMError, lvm.pvremove, "/not/existing/device")
        # pv already removed
        self.assertRaises(lvm.LVMError, lvm.pvremove, _LOOP_DEV0)

    #def testGetPossiblePhysicalExtents(self):
        # pass
        self.assertEqual(lvm.getPossiblePhysicalExtents(4),
                         filter(lambda pe: pe > 4, map(lambda power: 2**power, xrange(3, 25))))
        self.assertEqual(lvm.getPossiblePhysicalExtents(100000),
                         filter(lambda pe: pe > 100000, map(lambda power: 2**power, xrange(3, 25))))

    #def testGetMaxLVSize(self):
        # pass
        self.assertEqual(lvm.getMaxLVSize(), 16*1024**2)

    #def testSafeLVMName(self):
        # pass
        self.assertEqual(lvm.safeLvmName("/strange/lv*name5"), "strange_lvname5")

    #def testClampSize(self):
        # pass
        self.assertEqual(lvm.clampSize(10, 4), 8L)
        self.assertEqual(lvm.clampSize(10, 4, True), 12L)

    #def testVGUsedSpace(self):
        # TODO
        pass

    #def testVGFreeSpace(self):
        # TODO
        pass


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(LVMTestCase)


if __name__ == "__main__":
    unittest.main()
