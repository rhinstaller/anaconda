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
import re
import shutil
import subprocess
import tempfile
import unittest

CERT_CONTENT = """-----BEGIN CERTIFICATE-----
MIIBjTCCATOgAwIBAgIUWR5HO3v/0I80Ne0jQWVZFODuWLEwCgYIKoZIzj0EAwIw
FDESMBAGA1UEAwwJUlZURVNUIENBMB4XDTI0MTEyMDEzNTk1N1oXDTM0MTExODEz
NTk1N1owFDESMBAGA1UEAwwJUlZURVNUIENBMFkwEwYHKoZIzj0CAQYIKoZIzj0D
AQcDQgAELghFKGEgS8+5/2nx50W0xOqTrKc2Jz/rD/jfL0m4z4fkeAslCOkIKv74
0wfBXMngxi+OF/b3Vh8FmokuNBQO5qNjMGEwHQYDVR0OBBYEFOJarl9Xkd13sLzI
mHqv6aESlvuCMB8GA1UdIwQYMBaAFOJarl9Xkd13sLzImHqv6aESlvuCMA8GA1Ud
EwEB/wQFMAMBAf8wDgYDVR0PAQH/BAQDAgEGMAoGCCqGSM49BAMCA0gAMEUCIAet
7nyre42ReoRKoyHWLDsQmQDzoyU3FQdC0cViqOtrAiEAxYIL+XTTp7Xy9RNE4Xg7
yNWXfdraC/AfMM8fqsxlVJM=
-----END CERTIFICATE-----"""


class BaseTestCase(unittest.TestCase):
    def setUp(self):
        # create the directory used for file/folder tests
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        # remove the testing directory
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

    def test_cdrom(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""cdrom """)
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

        assert lines[0] == "inst.repo=cdrom", lines

    def test_harddrive(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""harddrive --partition=sda4 --dir=/path/to/tree""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

        assert lines[0] == "inst.repo=hd:sda4:/path/to/tree", lines

    def test_nfs(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""nfs --server=host.at.foo.com --dir=/path/to/tree --opts=nolock,timeo=50""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

        assert lines[0] == "inst.repo=nfs:nolock,timeo=50:host.at.foo.com:/path/to/tree", lines

    def test_nfs_2(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""nfs --server=host.at.foo.com --dir=/path/to/tree""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

        assert lines[0] == "inst.repo=nfs:host.at.foo.com:/path/to/tree", lines

    def test_url(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""url --url=https://host.at.foo.com/path/to/tree --noverifyssl --proxy=http://localhost:8123""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

        assert len(lines) == 3, lines
        assert lines[0] == "inst.repo=https://host.at.foo.com/path/to/tree", lines
        assert lines[1] == "rd.noverifyssl", lines
        assert lines[2] == "proxy=http://localhost:8123", lines

    def test_updates(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""updates http://host.at.foo.com/path/to/updates.img""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

        assert lines[0] == "live.updates=http://host.at.foo.com/path/to/updates.img", lines

    def test_mediacheck(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""mediacheck""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

        assert lines[0] == "rd.live.check", lines

    def test_driverdisk(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""driverdisk sda5""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

        assert lines[0] == "inst.dd=hd:sda5"

    def test_driverdisk_2(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""driverdisk --source=http://host.att.foo.com/path/to/dd""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

        assert lines[0] == "inst.dd=http://host.att.foo.com/path/to/dd", lines

    def test_network(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""network --device=link --bootproto=dhcp --activate""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

            assert re.search(r"ip=[^\s:]+:dhcp: bootdev=[^\s:]+", lines[0])

    def test_network_2(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""network --device=AA:BB:CC:DD:EE:FF --bootproto=dhcp --activate""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

            assert lines[0] == "ifname=ksdev0:aa:bb:cc:dd:ee:ff ip=ksdev0:dhcp: bootdev=ksdev0", lines

    def test_network_static(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""network --device=link --bootproto=dhcp --activate
network --device=lo --bootproto=static --ip=10.0.2.15 --netmask=255.255.255.0 --gateway=10.0.2.254 --nameserver=10.0.2.10
""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

            assert re.search(r"ip=[^\s:]+:dhcp: bootdev=[^\s:]+", lines[0])

    def test_network_team(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""network --device=link --bootproto=dhcp --activate
network --device team0 --activate --bootproto static --ip=10.34.102.222 --netmask=255.255.255.0 --gateway=10.34.102.254 --nameserver=10.34.39.2 --teamslaves="p3p1'{\"prio\": -10, \"sticky\": true}'" --teamconfig="{\"runner\": {\"name\": \"activebackup\"}}"
""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

            assert re.search(r"ip=[^\s:]+:dhcp: bootdev=[^\s:]+", lines[0])

    def test_network_bond(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""network --device=bond0 --mtu=1500 --bondslaves=enp4s0,enp7s0 --bondopts=mode=active-backup,primary=enp4s0 --bootproto=dhcp""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

            assert lines[0] == "ip=bond0:dhcp:1500 bootdev=bond0 bond=bond0:enp4s0,enp7s0:mode=active-backup,primary=enp4s0:1500"

    def test_network_bond_2(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            # no --mtu, no --bondopts
            ks_file.write("""network --device=bond0 --bondslaves=enp4s0,enp7s0 --bootproto=dhcp""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

            assert lines[0] == "ip=bond0:dhcp: bootdev=bond0 bond=bond0:enp4s0,enp7s0::"

    def test_network_bond_3(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            # no --bondopts
            ks_file.write("""network --device=bond0 --bondslaves=enp4s0,enp7s0 --mtu=1500 --bootproto=dhcp""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

            assert lines[0] == "ip=bond0:dhcp:1500 bootdev=bond0 bond=bond0:enp4s0,enp7s0::1500"

    def test_network_bridge(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""network --device=link --bootproto=dhcp --activate
network --device br0 --activate --bootproto dhcp --bridgeslaves=eth0 --bridgeopts=stp=6.0,forward_delay=2
""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

            assert re.search(r"ip=[^\s:]+:dhcp: bootdev=[^\s:]+", lines[0])

    def test_network_ipv6_only(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""network --noipv4 --hostname=blah.test.com --ipv6=1:2:3:4:5:6:7:8 --ipv6gateway=2001:beaf:cafe::1 --device lo --nameserver=1:1:1:1::,2:2:2:2::""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

            assert re.search(r"ip=\[1:2:3:4:5:6:7:8\]:.*", lines[0])

    def test_network_vlanid(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""network --device=link --bootproto=dhcp --activate
network --device=lo --vlanid=171
""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

            assert re.search(r"ip=[^\s:]+:dhcp: bootdev=[^\s:]+", lines[0])

    def test_network_vlan_interfacename(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""network --device=link --bootproto=dhcp --activate
network --device=lo --vlanid=171 --interfacename=vlan171
""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

            assert re.search(r"ip=[^\s:]+:dhcp: bootdev=[^\s:]+", lines[0])

    def test_displaymode(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""cmdline""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

            assert lines[0] == "inst.cmdline", lines

    def test_displaymode_2(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""graphical""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

            assert lines[0] == "inst.graphical", lines

    def test_displaymode_3(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""text""")
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

            assert lines[0] == "inst.text", lines

    def test_bootloader(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write("""bootloader --extlinux """)
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)

            assert lines[0] == "inst.extlinux", lines

    def _check_cert_file(self, cert_file, content):
        with open(cert_file) as f:
            # Anaconda adds `\n` to the value when dumping it
            assert f.read() == content+'\n'

    def test_certificate(self):
        filename = "rvtest.pem"
        cdir = os.path.join(self.tmpdir, "cert_dir/subdir")
        content = CERT_CONTENT
        ks_cert = f"""
%certificate --filename={filename} --dir={cdir}
{content}
%end
"""
        cert_file = os.path.join(cdir, filename)

        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write(ks_cert)
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)
            assert lines == []

        self._check_cert_file(cert_file, content)

        # Check existence for file for transport to root
        CERT_TRANSPORT_DIR = "/run/install/certificates"
        transport_file = os.path.join(CERT_TRANSPORT_DIR, cert_file)
        self._check_cert_file(transport_file, content)

    def test_certificate_existing(self):
        filename = "rvtest.pem"
        cdir = os.path.join(self.tmpdir, "cert_dir/subdir")
        content = CERT_CONTENT
        ks_cert = f"""
%certificate --filename={filename} --dir={cdir}
{content}
%end
"""
        cert_file = os.path.join(cdir, filename)

        # Existing file should be overwritten
        os.makedirs(cdir)
        open(cert_file, 'w')

        with tempfile.NamedTemporaryFile(mode="w+t") as ks_file:
            ks_file.write(ks_cert)
            ks_file.flush()
            lines = self.execParseKickstart(ks_file.name)
            assert lines == []

        self._check_cert_file(cert_file, content)

        # Check existence for file for transport to root
        CERT_TRANSPORT_DIR = "/run/install/certificates"
        transport_file = os.path.join(CERT_TRANSPORT_DIR, cert_file)
        self._check_cert_file(transport_file, content)
