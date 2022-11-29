#
# Copyright 2015 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use, modify,
# copy, or redistribute it subject to the terms and conditions of the GNU
# General Public License v.2.  This program is distributed in the hope that it
# will be useful, but WITHOUT ANY WARRANTY expressed or implied, including the
# implied warranties of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.  Any Red Hat
# trademarks that are incorporated in the source code or documentation are not
# subject to the GNU General Public License and may only be used or replicated
# with the express permission of Red Hat, Inc.

import os
import unittest
import tempfile
import shutil
import subprocess

class BaseTestCase(unittest.TestCase):
    def setUp(self):
        # create the directory used for file/folder tests
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        # remove the testing directory
        if self.tmpdir and os.path.isdir(self.tmpdir):
            try:
                with open(self.tmpdir + "/ks.info") as f:
                    for line in f:
                        if line.startswith("parsed_kickstart="):
                            filename = line.partition("=")[2].strip().replace('"', "")
                            os.remove(filename)
                            break
            except OSError:
                pass

            shutil.rmtree(self.tmpdir)

class ParseKickstartTestCase(BaseTestCase):
    @classmethod
    def setUpClass(cls):
        cls.command = os.path.abspath(os.path.join(os.environ["top_srcdir"], "dracut/parse-kickstart"))

    def execParseKickstart(self, ks_file):
        try:
            output = subprocess.check_output([self.command, "--tmpdir", self.tmpdir, ks_file], universal_newlines=True)
        except subprocess.CalledProcessError as e:
            return str(e).splitlines()
        return str(output).splitlines()

    def cdrom_test(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""cdrom """)
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

        self.assertEqual(lines[0], "inst.repo=cdrom", lines)

    def harddrive_test(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""harddrive --partition=sda4 --dir=/path/to/tree""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

        self.assertEqual(lines[0], "inst.repo=hd:sda4:/path/to/tree", lines)

    def nfs_test(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""nfs --server=host.at.foo.com --dir=/path/to/tree --opts=nolock,timeo=50""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

        self.assertEqual(lines[0], "inst.repo=nfs:nolock,timeo=50:host.at.foo.com:/path/to/tree", lines)

    def nfs_test_2(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""nfs --server=host.at.foo.com --dir=/path/to/tree""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

        self.assertEqual(lines[0], "inst.repo=nfs:host.at.foo.com:/path/to/tree", lines)

    def url_test(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""url --url=https://host.at.foo.com/path/to/tree --noverifyssl --proxy=http://localhost:8123""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

        self.assertEqual(len(lines), 3, lines)
        self.assertEqual(lines[0], "inst.repo=https://host.at.foo.com/path/to/tree", lines)
        self.assertEqual(lines[1], "rd.noverifyssl", lines)
        self.assertEqual(lines[2], "proxy=http://localhost:8123", lines)

    def updates_test(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""updates http://host.at.foo.com/path/to/updates.img""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

        self.assertEqual(lines[0], "live.updates=http://host.at.foo.com/path/to/updates.img", lines)

    def mediacheck_test(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""mediacheck""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

        self.assertEqual(lines[0], "rd.live.check", lines)

    def driverdisk_test(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""driverdisk sda5""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

        self.assertEqual(lines[0], "inst.dd=hd:sda5")

    def driverdisk_test_2(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""driverdisk --source=http://host.att.foo.com/path/to/dd""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

        self.assertEqual(lines[0], "inst.dd=http://host.att.foo.com/path/to/dd", lines)

    def network_test(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""network --device=link --bootproto=dhcp --activate""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

            self.assertRegex(lines[0], r"ip=[^\s:]+:dhcp: bootdev=[^\s:]+", lines)

    def network_test_2(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""network --device=AA:BB:CC:DD:EE:FF --bootproto=dhcp --activate""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

            self.assertEqual(lines[0], "ifname=ksdev0:aa:bb:cc:dd:ee:ff ip=ksdev0:dhcp: bootdev=ksdev0", lines)

    def network_static_test(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""network --device=link --bootproto=dhcp --activate
network --device=lo --bootproto=static --ip=10.0.2.15 --netmask=255.255.255.0 --gateway=10.0.2.254 --nameserver=10.0.2.10
""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

            self.assertRegex(lines[0], r"ip=[^\s:]+:dhcp: bootdev=[^\s:]+", lines)

            ifcfg_lines = sorted(open(self.tmpdir+"/ifcfg/ifcfg-lo").readlines())
            self.assertEqual(ifcfg_lines[0], "# Generated by parse-kickstart\n", ifcfg_lines)
            self.assertEqual(ifcfg_lines[1], 'BOOTPROTO="static"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[2], 'DEVICE="lo"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[3], 'DNS1="10.0.2.10"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[4], 'GATEWAY="10.0.2.254"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[5], 'IPADDR="10.0.2.15"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[6], 'IPV6INIT="yes"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[7], 'NETMASK="255.255.255.0"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[8], 'ONBOOT="no"\n', ifcfg_lines)
            self.assertTrue(ifcfg_lines[9].startswith("UUID="), ifcfg_lines)

    def network_team_test(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""network --device=link --bootproto=dhcp --activate
network --device team0 --activate --bootproto static --ip=10.34.102.222 --netmask=255.255.255.0 --gateway=10.34.102.254 --nameserver=10.34.39.2 --teamslaves="p3p1'{\"prio\": -10, \"sticky\": true}'" --teamconfig="{\"runner\": {\"name\": \"activebackup\"}}"
""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

            self.assertRegex(lines[0], r"ip=[^\s:]+:dhcp: bootdev=[^\s:]+", lines)

            team_lines = sorted(open(self.tmpdir+"/ifcfg/ifcfg-team0_slave_1").readlines())
            self.assertEqual(team_lines[0], "# Generated by parse-kickstart\n", team_lines)
            self.assertEqual(team_lines[1], 'DEVICE="p3p1"\n', team_lines)
            self.assertEqual(team_lines[2], 'DEVICETYPE="TeamPort"\n', team_lines)
            self.assertEqual(team_lines[3], 'NAME="team0 slave 1"\n', team_lines)
            self.assertEqual(team_lines[4], 'ONBOOT="yes"\n', team_lines)
            self.assertEqual(team_lines[5], 'TEAM_MASTER="team0"\n', team_lines)
            self.assertEqual(team_lines[6], 'TEAM_PORT_CONFIG="{prio: -10, sticky: true}"\n', team_lines)

    def network_bond_test(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""network --device=bond0 --mtu=1500 --bondslaves=enp4s0,enp7s0 --bondopts=mode=active-backup,primary=enp4s0 --bootproto=dhcp""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

            self.assertEqual(lines[0], "ip=bond0:dhcp:1500 bootdev=bond0 bond=bond0:enp4s0,enp7s0:mode=active-backup,primary=enp4s0:1500")

            ifcfg_lines = sorted(open(self.tmpdir+"/ifcfg/ifcfg-bond0_slave_1").readlines())
            self.assertEqual(ifcfg_lines[0], "# Generated by parse-kickstart\n", ifcfg_lines)
            self.assertTrue(ifcfg_lines[2].startswith("MASTER="), ifcfg_lines)
            self.assertEqual(ifcfg_lines[3], 'NAME="bond0 slave 1"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[4], 'ONBOOT="yes"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[5], 'TYPE="Ethernet"\n', ifcfg_lines)
            self.assertTrue(ifcfg_lines[6].startswith("UUID="), ifcfg_lines)

    def network_bond_test2(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            # no --mtu, no --bondopts
            ks_file.write("""network --device=bond0 --bondslaves=enp4s0,enp7s0 --bootproto=dhcp""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

            self.assertEqual(lines[0], "ip=bond0:dhcp: bootdev=bond0 bond=bond0:enp4s0,enp7s0::")

    def network_bond_test3(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            # no --bondopts
            ks_file.write("""network --device=bond0 --bondslaves=enp4s0,enp7s0 --mtu=1500 --bootproto=dhcp""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

            self.assertEqual(lines[0], "ip=bond0:dhcp:1500 bootdev=bond0 bond=bond0:enp4s0,enp7s0::1500")

            ifcfg_lines = sorted(open(self.tmpdir+"/ifcfg/ifcfg-bond0_slave_1").readlines())
            self.assertEqual(ifcfg_lines[0], "# Generated by parse-kickstart\n", ifcfg_lines)
            self.assertTrue(ifcfg_lines[2].startswith("MASTER="), ifcfg_lines)
            self.assertEqual(ifcfg_lines[3], 'NAME="bond0 slave 1"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[4], 'ONBOOT="yes"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[5], 'TYPE="Ethernet"\n', ifcfg_lines)
            self.assertTrue(ifcfg_lines[6].startswith("UUID="), ifcfg_lines)

    def network_bridge_test(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""network --device=link --bootproto=dhcp --activate
network --device br0 --activate --bootproto dhcp --bridgeslaves=eth0 --bridgeopts=stp=6.0,forward_delay=2
""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

            self.assertRegex(lines[0], r"ip=[^\s:]+:dhcp: bootdev=[^\s:]+", lines)

            ifcfg_lines = sorted(open(self.tmpdir+"/ifcfg/ifcfg-br0").readlines())
            self.assertEqual(ifcfg_lines[0], "# Generated by parse-kickstart\n", ifcfg_lines)
            self.assertEqual(ifcfg_lines[1], 'BOOTPROTO="dhcp"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[2], 'DELAY="2"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[3], 'DEVICE="br0"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[4], 'IPV6INIT="yes"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[5], 'NAME="Bridge connection br0"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[6], 'ONBOOT="yes"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[7], 'STP="6.0"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[8], 'TYPE="Bridge"\n', ifcfg_lines)
            self.assertTrue(ifcfg_lines[9].startswith("UUID="), ifcfg_lines)

            bridge_lines = sorted(open(self.tmpdir+"/ifcfg/ifcfg-br0_slave_1").readlines())
            self.assertEqual(bridge_lines[0], "# Generated by parse-kickstart\n", bridge_lines)
            self.assertEqual(bridge_lines[1], 'BRIDGE="br0"\n', bridge_lines)
            self.assertEqual(bridge_lines[3], 'NAME="br0 slave 1"\n', bridge_lines)
            self.assertEqual(bridge_lines[4], 'ONBOOT="yes"\n', bridge_lines)
            self.assertEqual(bridge_lines[5], 'TYPE="Ethernet"\n', bridge_lines)
            self.assertTrue(bridge_lines[6].startswith("UUID="), bridge_lines)

    def network_ipv6_only_test(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""network --noipv4 --hostname=blah.test.com --ipv6=1:2:3:4:5:6:7:8 --ipv6gateway=2001:beaf:cafe::1 --device lo --nameserver=1:1:1:1::,2:2:2:2::""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

            self.assertRegex(lines[0], r"ip=\[1:2:3:4:5:6:7:8\]:.*")

            ifcfg_lines = sorted(open(self.tmpdir+"/ifcfg/ifcfg-lo").readlines())
            self.assertEqual(ifcfg_lines[1], 'DEVICE="lo"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[2], 'DNS1="1:1:1:1::"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[3], 'DNS2="2:2:2:2::"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[4], 'IPV6ADDR="1:2:3:4:5:6:7:8"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[5], 'IPV6INIT="yes"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[6], 'IPV6_AUTOCONF="no"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[7], 'IPV6_DEFAULTGW="2001:beaf:cafe::1"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[8], 'ONBOOT="yes"\n', ifcfg_lines)
            self.assertTrue(ifcfg_lines[9].startswith("UUID="), ifcfg_lines)

    def network_vlanid_test(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""network --device=link --bootproto=dhcp --activate
network --device=lo --vlanid=171
""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

            self.assertRegex(lines[0], r"ip=[^\s:]+:dhcp: bootdev=[^\s:]+", lines)

            ifcfg_lines = sorted(open(self.tmpdir+"/ifcfg/ifcfg-lo.171").readlines())
            self.assertEqual(ifcfg_lines[1], 'BOOTPROTO="dhcp"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[2], 'IPV6INIT="yes"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[3], 'NAME="VLAN connection lo.171"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[4], 'ONBOOT="no"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[5], 'PHYSDEV="lo"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[6], 'TYPE="Vlan"\n', ifcfg_lines)
            self.assertTrue(ifcfg_lines[7].startswith("UUID="), ifcfg_lines)
            self.assertEqual(ifcfg_lines[8], 'VLAN="yes"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[9], 'VLAN_ID="171"\n', ifcfg_lines)

    def network_vlan_interfacename_test(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""network --device=link --bootproto=dhcp --activate
network --device=lo --vlanid=171 --interfacename=vlan171
""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

            self.assertRegex(lines[0], r"ip=[^\s:]+:dhcp: bootdev=[^\s:]+", lines)

            ifcfg_lines = sorted(open(self.tmpdir+"/ifcfg/ifcfg-vlan171").readlines())
            self.assertEqual(ifcfg_lines[1], 'BOOTPROTO="dhcp"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[2], 'DEVICE="vlan171"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[3], 'IPV6INIT="yes"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[4], 'NAME="VLAN connection vlan171"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[5], 'ONBOOT="no"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[6], 'PHYSDEV="lo"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[7], 'TYPE="Vlan"\n', ifcfg_lines)
            self.assertTrue(ifcfg_lines[8].startswith("UUID="), ifcfg_lines)
            self.assertEqual(ifcfg_lines[9], 'VLAN="yes"\n', ifcfg_lines)
            self.assertEqual(ifcfg_lines[10], 'VLAN_ID="171"\n', ifcfg_lines)


    def displaymode_test(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""cmdline""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

            self.assertEqual(lines[0], "inst.cmdline", lines)

    def displaymode_test_2(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""graphical""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

            self.assertEqual(lines[0], "inst.graphical", lines)

    def displaymode_test_3(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""text""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

            self.assertEqual(lines[0], "inst.text", lines)

    def bootloader_test(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""bootloader --extlinux """)
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

            self.assertEqual(lines[0], "extlinux", lines)
