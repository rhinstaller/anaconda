#!/usr/bin/python
import baseclass
import unittest
from mock import acceptance

class MPathTestCase(baseclass.DevicelibsTestCase):
    def testMPath(self):
        import storage.devicelibs.mpath as mpath

    @acceptance
    def testMPath(self):
        ##
        ## parseMultipathOutput
        ## 
        output="""\
create: mpathb (1ATA     ST3120026AS                                         5M) undef ATA,ST3120026AS
size=112G features='0' hwhandler='0' wp=undef
`-+- policy='round-robin 0' prio=1 status=undef
  `- 2:0:0:0 sda 8:0  undef ready running
create: mpatha (36006016092d21800703762872c60db11) undef DGC,RAID 5
size=10G features='1 queue_if_no_path' hwhandler='1 emc' wp=undef
`-+- policy='round-robin 0' prio=2 status=undef
  |- 6:0:0:0 sdb 8:16 undef ready running
  `- 7:0:0:0 sdc 8:32 undef ready running
"""
        topology = mpath.parseMultipathOutput(output)
        expected = {'mpatha':['sdb','sdc'], 'mpathb':['sda']}
        self.assertEqual(topology, expected)

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(MPathTestCase)

if __name__ == '__main__':
    unittest.main()
