#
# Copyright (C) 2017  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

import unittest
import os
from contextlib import contextmanager

from mock import Mock

from pyanaconda.dbus.observer import DBusObjectObserver
from pyanaconda.modules.boss.kickstart_manager import KickstartManager,\
    SplitKickstartSectionParsingError, SplitKickstartMissingIncludeError

KICKSTART1 = """
text

%pre
echo PRE
%end

url --url=http://download.eng.brq.redhat.com/pub/fedora/development/25/Server/x86_64/os/.
lang en_US.UTF-8
keyboard --vckeymap=us --xlayouts='us'
rootpw --plaintext chrchl
selinux --enforcing
firstboot --disable
authconfig --passalgo=sha512 --enableshadow
timezone --utc Asia/Tokyo

network --device ens3
network --device ens4 --activate
%include {}

%addon pony --fly=True
%end

bootloader --location=mbr --boot-drive=vda --driveorder=vda
clearpart --all --drives=vda
ignoredisk --only-use=vda

firewall --enabled

# Partitioning conflicts with autopart
#part /boot --fstype=xfs --onpart=vda1
#part pv.100000 --size=18436 --ondisk=vda
#volgroup Vol00 --pesize=4096 pv.100000
#logvol / --fstype=xfs --name=lv_root --vgname=Vol00 --size=15360
#logvol /home --fstype=xfs --name=lv_home --vgname=Vol00 --size=1024
#logvol swap --fstype=swap --name=lv_swap --vgname=Vol00 --size=2048

autopart --encrypted --passphrase=chrchl --type=lvm

%addon scorched --planet=Eearth
%end

%packages --ignoremissing
@core
@PARSE_ERROR
@base
%end

%post --nochroot --interpreter /usr/bin/bash

echo "POST1"
%end

%post --nochroot --interpreter /usr/bin/bash
echo "POST2"
%end
""".strip()

# Kickstart with
# - 2 levels of %include
# - sections in included kickstart
INCLUDE_LEVEL_1_FILENAME = "ks.manager.test.include1.cfg"
INCLUDE_LEVEL_2_FILENAME = "ks.manager.test.include2.cfg"
kickstart_include = [
    ("ks.manager.test.include.cfg", KICKSTART1.format(INCLUDE_LEVEL_1_FILENAME).strip()),
    (INCLUDE_LEVEL_1_FILENAME, """
network --device=ens51 --activate
%include {}
network --device=ens55 --activate
network --device=ens56 --activate
network --hostname=PARSE_ERROR
repo --name=repo1 --baseurl=http://bla.bla/repo1
%post
echo "POST_include1"
%end
""".format(INCLUDE_LEVEL_2_FILENAME).strip()),
    (INCLUDE_LEVEL_2_FILENAME, """
repo --name=repo1 --baseurl=http://bla.bla/repo1
network --device=ens541 --activate
%post --nochroot --interpreter /usr/bin/bash
echo "POST_include2"
%end
""".strip())
]

# Expected dispatched kickstarts

m1_kickstart = """
network --device ens3
network --device ens4 --activate
network --device=ens51 --activate
network --device=ens541 --activate
network --device=ens55 --activate
network --device=ens56 --activate
network --hostname=PARSE_ERROR
firewall --enabled
""".lstrip()

m2_kickstart = """
%addon pony --fly=True
%end
""".lstrip()

m3_kickstart = """
%packages --ignoremissing
@core
@PARSE_ERROR
@base
%end
""".lstrip()

unprocessed_kickstart = """
text
%pre
echo PRE
%end
url --url=http://download.eng.brq.redhat.com/pub/fedora/development/25/Server/x86_64/os/.
lang en_US.UTF-8
keyboard --vckeymap=us --xlayouts='us'
rootpw --plaintext chrchl
selinux --enforcing
firstboot --disable
authconfig --passalgo=sha512 --enableshadow
timezone --utc Asia/Tokyo
repo --name=repo1 --baseurl=http://bla.bla/repo1
%post --nochroot --interpreter /usr/bin/bash
echo "POST_include2"
%end
repo --name=repo1 --baseurl=http://bla.bla/repo1
%post
echo "POST_include1"
%end
bootloader --location=mbr --boot-drive=vda --driveorder=vda
clearpart --all --drives=vda
ignoredisk --only-use=vda
autopart --encrypted --passphrase=chrchl --type=lvm
%addon scorched --planet=Eearth
%end
%post --nochroot --interpreter /usr/bin/bash

echo "POST1"
%end
%post --nochroot --interpreter /usr/bin/bash
echo "POST2"
%end
""".lstrip()


class KickstartManagerTestCase(unittest.TestCase):

    def setUp(self):
        self._kickstart_include = kickstart_include
        self._m1_kickstart = m1_kickstart
        self._m2_kickstart = m2_kickstart
        self._m3_kickstart = m3_kickstart
        self._unprocessed_kickstart = unprocessed_kickstart

    @contextmanager
    def _create_ks_files(self, kickstart):
        """Context with all the kickstart files defined in kickstart list created.

        Yields file name of the main file.
        """
        for filename, content in kickstart:
            with open(filename, "w") as f:
                f.write(content)
        yield kickstart[0][0]
        for filename, _content in kickstart:
            os.remove(filename)

    def distribute_test(self):
        manager = KickstartManager()
        module1 = TestModule(commands=["network", "firewall"])
        module2 = TestModule(addons=["pony"])
        module3 = TestModule(sections=["packages"])
        module4 = TestModule(addons=["scorched"])
        m1_observer = TestModuleObserver("1", "1", module1)
        m2_observer = TestModuleObserver("2", "2", module2)
        m3_observer = TestModuleObserver("3", "3", module3)
        unavailable_observer = TestModuleObserver("4", "4", module4)
        unavailable_observer._is_service_available = False

        manager.module_observers = [m1_observer, m2_observer, m3_observer,
                                    unavailable_observer]
        with self._create_ks_files(self._kickstart_include) as filename:
            manager.split(filename)
        errors = manager.distribute()

        self.assertEqual(module1.kickstart, self._m1_kickstart)
        self.assertEqual(module2.kickstart, self._m2_kickstart)
        self.assertEqual(module3.kickstart, self._m3_kickstart)
        self.assertEqual(module4.kickstart, "")
        self.assertEqual(manager.unprocessed_kickstart, self._unprocessed_kickstart)

        expected_errors = {("1", 5, 'ks.manager.test.include1.cfg'),
                           ("3", 42, 'ks.manager.test.include.cfg')}
        actual_errors = set()
        for service_name, (lineno, file_name), _msg in errors:
            actual_errors.add((service_name, lineno, file_name))
        self.assertEqual(actual_errors, expected_errors)

    def unknown_section_split_test(self):
        ks_content = """
network --device=ens3
%unknown_section
blah
%end
""".strip()
        manager = KickstartManager()
        with self._create_ks_files([("ks.mgr.test.unknown_sect.cfg", ks_content)]) as filename:
            self.assertRaises(SplitKickstartSectionParsingError, manager.split, filename)

    def missing_section_end_split_test(self):
        ks_content = """
network --device=ens3
%packages
blah
""".strip()
        manager = KickstartManager()
        with self._create_ks_files([("ks.mgr.test.missing_end.cfg", ks_content)]) as filename:
            self.assertRaises(SplitKickstartSectionParsingError, manager.split, filename)

    def missing_include_split_test(self):
        ks_content = """
network --device=ens3
%include missing_include.cfg
""".strip()
        manager = KickstartManager()
        with self._create_ks_files([("ks.mgr.test.missing_include.cfg", ks_content)]) as filename:
            self.assertRaises(SplitKickstartMissingIncludeError, manager.split, filename)


class TestModuleObserver(DBusObjectObserver):

    def __init__(self, service_name, object_path, test_module):
        super().__init__(Mock(), service_name, object_path)
        self._proxy = test_module
        self._is_service_available = True


class TestModule(object):

    def __init__(self, commands=None, sections=None, addons=None):
        self.kickstart_commands = commands or []
        self.kickstart_sections = sections or []
        self.kickstart_addons = addons or []
        self.kickstart = ""

    def KickstartSections(self):
        return self.kickstart_sections

    def KickstartAddons(self):
        return self.kickstart_addons

    def KickstartCommands(self):
        return self.kickstart_commands

    def configure_with_kickstart(self, kickstart):
        """Mock parsing for now.

        Returns parse error if PARSE_ERROR string is found in kickstart.
        """
        lineno, msg = (0, "")
        for lnum, line in enumerate(kickstart.splitlines(), 1):
            if "PARSE_ERROR" in line:
                lineno, msg = (lnum, "Mocked parse error: \"PARSE_ERROR\" found")
                break
        return (lineno, msg)

    def ConfigureWithKickstart(self, kickstart):
        self.kickstart = kickstart
        return self.configure_with_kickstart(kickstart)
