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

import os
import unittest
from contextlib import contextmanager
from unittest.mock import Mock

from pyanaconda.modules.boss.kickstart_manager import KickstartManager
from pyanaconda.modules.boss.module_manager.module_observer import ModuleObserver
from pyanaconda.modules.common.structures.kickstart import (
    KickstartMessage,
    KickstartReport,
)

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

m123_kickstart = """
network --device ens3
network --device ens4 --activate
network --device=ens51 --activate
network --device=ens541 --activate
network --device=ens55 --activate
network --device=ens56 --activate
network --hostname=PARSE_ERROR
firewall --enabled

%addon pony --fly=True
%end

%packages --ignoremissing
@core
@PARSE_ERROR
@base
%end
""".strip()

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
        self._m123_kickstart = m123_kickstart

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

    def _get_module_observer(self, service_path, module_proxy, available=True):
        observer = ModuleObserver(Mock(), service_path)
        observer._proxy = module_proxy
        observer._is_service_available = available
        return observer

    def test_distribute(self):
        manager = KickstartManager()

        module1 = TestModule(commands=["network", "firewall"])
        module2 = TestModule(addons=["pony"])
        module3 = TestModule(sections=["packages"])
        module4 = TestModule(addons=["scorched"])

        m1_observer = self._get_module_observer("1", module1)
        m2_observer = self._get_module_observer("2", module2)
        m3_observer = self._get_module_observer("3", module3)
        m4_observer = self._get_module_observer("4", module4, available=False)

        manager.on_module_observers_changed([
            m1_observer,
            m2_observer,
            m3_observer,
            m4_observer
        ])

        with self._create_ks_files(self._kickstart_include) as filename:
            report = manager.read_kickstart_file(filename)

        assert module1.kickstart == self._m1_kickstart
        assert module2.kickstart == self._m2_kickstart
        assert module3.kickstart == self._m3_kickstart
        assert module4.kickstart == ""

        assert report.is_valid() is False
        assert len(report.get_messages()) == 2

        error = report.get_messages()[0]
        assert error.module_name == "1"
        assert error.file_name == "ks.manager.test.include1.cfg"
        assert error.line_number == 5
        assert error.message == "Mocked parse error: \"PARSE_ERROR\" found"

        error = report.get_messages()[1]
        assert error.module_name == "3"
        assert error.file_name == "ks.manager.test.include.cfg"
        assert error.line_number == 41
        assert error.message == "Mocked parse error: \"PARSE_ERROR\" found"

        assert manager.generate_kickstart() == self._m123_kickstart

    def test_nothing_to_parse(self):
        ks_content = ""
        manager = KickstartManager()
        with self._create_ks_files([("ks.mgr.test.empty.cfg", ks_content)]) as filename:
            report = manager.read_kickstart_file(filename)

        assert report.is_valid() is True
        assert len(report.get_messages()) == 0

        assert manager.generate_kickstart() == ""

    def test_unknown_section_split(self):
        ks_content = """
network --device=ens3
%unknown_section
blah
%end
""".strip()
        manager = KickstartManager()
        with self._create_ks_files([("ks.mgr.test.unknown_sect.cfg", ks_content)]) as filename:
            report = manager.read_kickstart_file(filename)

        assert report.is_valid() is False
        assert len(report.get_messages()) == 1

        error = report.get_messages()[0]
        assert error.module_name == "org.fedoraproject.Anaconda.Boss"
        assert error.file_name == "ks.mgr.test.unknown_sect.cfg"
        assert error.line_number == 2
        assert error.message == 'Unknown kickstart section: %unknown_section'

    def test_missing_section_end_split(self):
        ks_content = """
network --device=ens3
%packages
blah
""".strip()
        manager = KickstartManager()
        with self._create_ks_files([("ks.mgr.test.missing_end.cfg", ks_content)]) as filename:
            report = manager.read_kickstart_file(filename)

        assert report.is_valid() is False
        assert len(report.get_messages()) == 1

        error = report.get_messages()[0]
        assert error.module_name == "org.fedoraproject.Anaconda.Boss"
        assert error.file_name == "ks.mgr.test.missing_end.cfg"
        assert error.line_number == 3
        assert error.message == 'Section %packages does not end with %end.'

    def test_missing_include_split(self):
        ks_content = """
network --device=ens3
%include missing_include.cfg
""".strip()
        manager = KickstartManager()
        with self._create_ks_files([("ks.mgr.test.missing_include.cfg", ks_content)]) as filename:
            report = manager.read_kickstart_file(filename)

        assert report.is_valid() is False
        assert len(report.get_messages()) == 1

        error = report.get_messages()[0]
        assert error.module_name == "org.fedoraproject.Anaconda.Boss"
        assert error.file_name == "ks.mgr.test.missing_include.cfg"
        assert error.line_number == 0
        assert error.message == \
            "Unable to open input kickstart file: Error opening file: " \
            "[Errno 2] No such file or directory: 'missing_include.cfg'"


class TestModule(object):

    def __init__(self, commands=None, sections=None, addons=None):
        self.kickstart_commands = commands or []
        self.kickstart_sections = sections or []
        self.kickstart_addons = addons or []
        self.kickstart = ""

    @property
    def KickstartSections(self):
        return self.kickstart_sections

    @property
    def KickstartAddons(self):
        return self.kickstart_addons

    @property
    def KickstartCommands(self):
        return self.kickstart_commands

    def ReadKickstart(self, kickstart):
        """Mock parsing for now.

        Returns parse error if PARSE_ERROR string is found in kickstart.
        """
        self.kickstart = kickstart
        report = KickstartReport()

        for lnum, line in enumerate(kickstart.splitlines(), 1):
            if "PARSE_ERROR" in line:
                data = KickstartMessage()
                data.message = "Mocked parse error: \"PARSE_ERROR\" found"
                data.line_number = lnum
                report.error_messages.append(data)

        return KickstartReport.to_structure(report)

    def GenerateKickstart(self):
        """Mock generating a kickstart."""
        return self.kickstart
