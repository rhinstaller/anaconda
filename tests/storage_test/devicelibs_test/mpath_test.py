#!/usr/bin/python
import mock

class MPathTestCase(mock.TestCase):

    # creating devices, user_friendly_names set to yes
    output1 = """\
create: mpathb (1ATA     ST3120026AS                                         5M) undef ATA,ST3120026AS
size=112G features='0' hwhandler='0' wp=undef
`-+- policy='round-robin 0' prio=1 status=undef
  `- 2:0:0:0 sda 8:0  undef ready running
create: mpatha (36006016092d21800703762872c60db11) undef DGC,RAID 5
size=10G features='1 queue_if_no_path' hwhandler='1 emc' wp=undef
`-+- policy='round-robin 0' prio=2 status=undef
  |- 6:0:0:0 sdb 8:16 undef ready running
  `- 7:0:0:0 sdc 8:32 undef ready running\
"""

    # listing existing devices, user_friendly_names set to yes
    output2 = """\
mpathb (3600a0b800067fcc9000001f34d23ff88) dm-1 IBM,1726-4xx  FAStT
size=100G features='0' hwhandler='1 rdac' wp=rw
`-+- policy='round-robin 0' prio=-1 status=active
  |- 1:0:0:0 sda 8:0  active undef running
  `- 2:0:0:0 sdc 8:32 active undef running
mpatha (3600a0b800067fabc000067694d23fe6e) dm-0 IBM,1726-4xx  FAStT
size=100G features='0' hwhandler='1 rdac' wp=rw
`-+- policy='round-robin 0' prio=-1 status=active
  |- 1:0:0:1 sdb 8:16 active undef running
  `- 2:0:0:1 sdd 8:48 active undef running
"""

    # creating devices, user_friendly_names set to no
    output3 = """\
create: 3600a0b800067fabc000067694d23fe6e undef IBM,1726-4xx  FAStT
size=100G features='1 queue_if_no_path' hwhandler='1 rdac' wp=undef
`-+- policy='round-robin 0' prio=6 status=undef
  |- 1:0:0:1 sdb 8:16 undef ready running
  `- 2:0:0:1 sdd 8:48 undef ready running
create: 3600a0b800067fcc9000001f34d23ff88 undef IBM,1726-4xx  FAStT
size=100G features='1 queue_if_no_path' hwhandler='1 rdac' wp=undef
`-+- policy='round-robin 0' prio=3 status=undef
  |- 1:0:0:0 sda 8:0  undef ready running
  `- 2:0:0:0 sdc 8:32 undef ready running\
"""

    # listing existing devices, user_friendly_names set to no
    output4 = """\
3600a0b800067fcc9000001f34d23ff88 dm-1 IBM,1726-4xx  FAStT
size=100G features='0' hwhandler='1 rdac' wp=rw
`-+- policy='round-robin 0' prio=-1 status=active
  |- 1:0:0:0 sda 8:0  active undef running
  `- 2:0:0:0 sdc 8:32 active undef running
3600a0b800067fabc000067694d23fe6e dm-0 IBM,1726-4xx  FAStT
size=100G features='0' hwhandler='1 rdac' wp=rw
`-+- policy='round-robin 0' prio=-1 status=active
  |- 1:0:0:1 sdb 8:16 active undef running
  `- 2:0:0:1 sdd 8:48 active undef running
"""

    def setUp(self):
        self.setupModules(
            ['_isys', 'logging', 'anaconda_log', 'block'])

    def tearDown(self):
        self.tearDownModules()

    def testParse(self):
        from pyanaconda.storage.devicelibs import mpath
        topology = mpath.parseMultipathOutput(self.output1)
        self.assertEqual(topology,
                         {'mpatha':['sdb','sdc'], 'mpathb':['sda']})
        topology = mpath.parseMultipathOutput(self.output2)
        self.assertEqual(topology,
                         {'mpathb':['sda','sdc'], 'mpatha':['sdb', 'sdd']})
        topology = mpath.parseMultipathOutput(self.output3)
        self.assertEqual(topology,
                         {'3600a0b800067fabc000067694d23fe6e' : ['sdb','sdd'],
                          '3600a0b800067fcc9000001f34d23ff88' : ['sda', 'sdc']})
        topology = mpath.parseMultipathOutput(self.output4)
        self.assertEqual(topology,
                         {'3600a0b800067fabc000067694d23fe6e' : ['sdb','sdd'],
                          '3600a0b800067fcc9000001f34d23ff88' : ['sda', 'sdc']})

def suite():
    return unittest.TestLoader().loadTestsFromTestCase(MPathTestCase)
