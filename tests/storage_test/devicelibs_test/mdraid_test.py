#!/usr/bin/python
import baseclass
import unittest
import time
from mock import acceptance

class MDRaidTestCase(baseclass.DevicelibsTestCase):

    def testMDRaid(self):
        _LOOP_DEV0 = self._loopMap[self._LOOP_DEVICES[0]]
        _LOOP_DEV1 = self._loopMap[self._LOOP_DEVICES[1]]

        import storage.devicelibs.mdraid as mdraid

    @acceptance
    def testMDRaid(self):
        ##
        ## getRaidLevels
        ##
        # pass
        self.assertEqual(mdraid.getRaidLevels(), mdraid.getRaidLevels())

        ##
        ## get_raid_min_members
        ##
        # pass
        self.assertEqual(mdraid.get_raid_min_members(mdraid.RAID0), 2)
        self.assertEqual(mdraid.get_raid_min_members(mdraid.RAID1), 2)
        self.assertEqual(mdraid.get_raid_min_members(mdraid.RAID5), 3)
        self.assertEqual(mdraid.get_raid_min_members(mdraid.RAID6), 4)
        self.assertEqual(mdraid.get_raid_min_members(mdraid.RAID10), 2)

        # fail
        # unsupported raid
        self.assertRaises(ValueError, mdraid.get_raid_min_members, 8)

        ##
        ## get_raid_max_spares
        ##
        # pass
        self.assertEqual(mdraid.get_raid_max_spares(mdraid.RAID0, 5), 0)
        self.assertEqual(mdraid.get_raid_max_spares(mdraid.RAID1, 5), 3)
        self.assertEqual(mdraid.get_raid_max_spares(mdraid.RAID5, 5), 2)
        self.assertEqual(mdraid.get_raid_max_spares(mdraid.RAID6, 5), 1)
        self.assertEqual(mdraid.get_raid_max_spares(mdraid.RAID10, 5), 3)

        # fail
        # unsupported raid
        self.assertRaises(ValueError, mdraid.get_raid_max_spares, 8, 5)

        ##
        ## mdcreate
        ##
        # pass
        self.assertEqual(mdraid.mdcreate("/dev/md0", 1, [_LOOP_DEV0, _LOOP_DEV1]), None)
        # wait for raid to settle
        time.sleep(2)

        # fail
        self.assertRaises(mdraid.MDRaidError, mdraid.mdcreate, "/dev/md1", 1, ["/not/existing/dev0", "/not/existing/dev1"])

        ##
        ## mddeactivate
        ##
        # pass
        self.assertEqual(mdraid.mddeactivate("/dev/md0"), None)

        # fail
        self.assertRaises(mdraid.MDRaidError, mdraid.mddeactivate, "/not/existing/md")

        ##
        ## mdadd
        ##
        # pass
        # TODO

        # fail
        self.assertRaises(mdraid.MDRaidError, mdraid.mdadd, "/not/existing/device")

        ##
        ## mdactivate
        ##
        # pass
        self.assertEqual(mdraid.mdactivate("/dev/md0", [_LOOP_DEV0, _LOOP_DEV1], super_minor=0), None)
        # wait for raid to settle
        time.sleep(2)

        # fail
        self.assertRaises(mdraid.MDRaidError, mdraid.mdactivate, "/not/existing/md", super_minor=1)
        # requires super_minor or uuid
        self.assertRaises(ValueError, mdraid.mdactivate, "/dev/md1")

        ##
        ## mddestroy
        ##
        # pass
        # deactivate first
        self.assertEqual(mdraid.mddeactivate("/dev/md0"), None)

        self.assertEqual(mdraid.mddestroy(_LOOP_DEV0), None)
        self.assertEqual(mdraid.mddestroy(_LOOP_DEV1), None)

        # fail
        # not a component
        self.assertRaises(mdraid.MDRaidError, mdraid.mddestroy, "/dev/md0")
        self.assertRaises(mdraid.MDRaidError, mdraid.mddestroy, "/not/existing/device")


def suite():
    return unittest.TestLoader().loadTestsFromTestCase(MDRaidTestCase)


if __name__ == "__main__":
    unittest.main()
