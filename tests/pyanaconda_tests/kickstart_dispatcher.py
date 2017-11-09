#
# Radek Vykydal <rvykydal@redhat.com>
#
# Copyright 2017 Red Hat, Inc.
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
#

import unittest
import os
import shlex
from contextlib import contextmanager

from pyanaconda.kickstart_dispatcher import KickstartCommandOrSection,  FilterKickstartParser
from pykickstart.version import returnClassForVersion
from pykickstart.errors import KickstartParseError, KickstartError

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
@base
%end

%post --nochroot --interpreter /usr/bin/bash

echo "POST1"
%end

%post --nochroot --interpreter /usr/bin/bash
echo "POST2"
%end
""".strip()


kickstart_flat=[("ks.test.flat.cfg", KICKSTART1.replace("%include {}", ""))]

# Kickstart with
# - 2 levels of %include
# - sections in included kickstart
INCLUDE_LEVEL_1_FILENAME = "ks.test.include1.cfg"
INCLUDE_LEVEL_2_FILENAME = "ks.test.include2.cfg"
kickstart_include=[
("ks.test.include.cfg", KICKSTART1.format(INCLUDE_LEVEL_1_FILENAME).strip()),
(INCLUDE_LEVEL_1_FILENAME, """
network --device=ens51 --activate
%include {}
network --device=ens55 --activate
network --device=ens56 --activate
repo --name=repo1 --baseurl=http://bla.bla/repo1
%packages
@include1
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

kickstart_include_result_kickstart = """
%pre
echo PRE
%end
network --device ens3
network --device ens4 --activate
network --device=ens51 --activate
network --device=ens541 --activate
%post --nochroot --interpreter /usr/bin/bash
echo "POST_include2"
%end
network --device=ens55 --activate
network --device=ens56 --activate
%packages
@include1
%end
%addon pony --fly=True
%end
firewall --enabled
%addon scorched --planet=Eearth
%end
%packages --ignoremissing
@core
@base
%end
%post --nochroot --interpreter /usr/bin/bash

echo "POST1"
%end
%post --nochroot --interpreter /usr/bin/bash
echo "POST2"
%end
""".lstrip()

class FilterKickstartParserTest(unittest.TestCase):

    def setUp(self):
        self._kickstart_flat = kickstart_flat
        self._kickstart_include = kickstart_include

    def simple_test(self):
        """This test should demonstrate usage and output of the filter parser."""
        ks_content = """
network --device=ens3 --activate
firewall --enabled
%addon pony --fly=True
%end
""".lstrip()
        filename = "ks.test.simple.cfg"
        valid_sections = ["%pre", "%pre-install", "%post", "%onerror", "%traceback", "%packages", "%addon", "%anaconda"]
        commands = ["network", "firewall"]
        sections = ["%addon"]

        handler = returnClassForVersion()
        ksparser = FilterKickstartParser(handler, valid_sections)

        # Reading kickstart from file

        line1 = KickstartCommandOrSection("network --device=ens3 --activate\n", 1, filename)
        line2 = KickstartCommandOrSection("firewall --enabled\n", 2, filename)
        line3 = KickstartCommandOrSection("%addon pony --fly=True\n%end\n", 3, filename)
        expected_result = [line1, line2, line3]

        with open(filename, "w") as f:
            f.write(ks_content)
        result = ksparser.filter(filename, commands, sections)
        os.remove(filename)

        self.assertEqual(result, expected_result)
        self.assertEqual(ksparser.kickstart_from_result(result), ks_content)

        # Reading kickstart from string

        filename = ksparser.unknown_filename
        line1 = KickstartCommandOrSection("network --device=ens3 --activate\n", 1, filename)
        line2 = KickstartCommandOrSection("firewall --enabled\n", 2, filename)
        line3 = KickstartCommandOrSection("%addon pony --fly=True\n%end\n", 3, filename)
        expected_result = [line1, line2, line3]

        result = ksparser.filter_from_string(ks_content, commands, sections)

        self.assertEqual(result, expected_result)
        self.assertEqual(ksparser.kickstart_from_result(result), ks_content)

    @contextmanager
    def _prepare_kickstart(self, kickstart_file_specs):
        file_lines_map = {}
        for filename, content in kickstart_file_specs:
            with open(filename, "w") as f:
                f.write(content)
            file_lines_map[filename] = content.splitlines(keepends=True)
        yield file_lines_map
        for filename, _content in kickstart_file_specs:
            os.remove(filename)

    def _check_kickstart(self, ksparser, kickstart, commands=None, sections=None):
        with self._prepare_kickstart(kickstart) as file_lines_map:
            filename = kickstart[0][0]
            result = ksparser.filter(filename, commands, sections)
            self._check_references(result, file_lines_map)
            self._check_nothing_is_missing(result, kickstart, commands, sections)
        return result

    def _check_kickstart_from_string(self, ksparser, kickstart, commands=None, sections=None):
        """Note: works only for kickstart without %include"""
        filename, content = kickstart[0]
        file_lines_map = {filename or FilterKickstartParser.unknown_filename: content.splitlines(keepends=True)}
        result = ksparser.filter_from_string(content, commands, sections, filename)
        self._check_references(result, file_lines_map)
        self._check_nothing_is_missing(result, kickstart, commands, sections)
        return result

    def _check_references(self, result, file_lines_map):
        """Checks that the line/file references in result are correct.

            Uses shlex (as pykickstart) to parse section headers.
        """
        for line_or_section, lineno, filename in result:
            original_kickstart_line = file_lines_map[filename][lineno-1]
            if line_or_section.strip()[0] == "%":
                # section
                # We keep only references to headers.
                header = line_or_section.strip().split("\n")[0]
                # Headers are not stored as source lines but go through shlex
                # parsing before we can store them in result.
                self.assertEqual(shlex.split(header), shlex.split(original_kickstart_line))
            else:
                # command
                self.assertEqual(line_or_section, original_kickstart_line)

    def _check_nothing_is_missing(self, result, kickstart, commands, sections):
        """Checks that all specified lines in kickstart are in the result.

            Uses shlex (as pykickstart) to identify required sections and commands.
        """
        # Note: assumes all files are actually included in main kickstart
        commands = commands or []
        sections = sections or []
        ks_count = {}
        for _filename, content in kickstart:
            self._count_ks_lines(ks_count, content.splitlines(), commands, sections)

        result_count = {}
        # Count only first line of content because sections are stored complete
        self._count_ks_lines(result_count, (element.content.split("\n")[0] for element in result),
                             commands, sections)
        self.assertEqual(ks_count, result_count)

    def _count_ks_lines(self, count_dict, lines, commands, sections):
        for line in lines:
            args = shlex.split(line)
            if not args:
                continue
            token = args[0]
            line = " ".join(args)
            if (token.startswith("%") and token in sections) \
               or (not token.startswith("%") and token in commands):
                if line in count_dict:
                    count_dict[line] = count_dict[line] + 1
                else:
                    count_dict[line] = 1

    def filter_test(self):
        valid_sections = ["%pre", "%pre-install", "%post", "%onerror", "%traceback", "%packages", "%addon", "%anaconda"]
        handler = returnClassForVersion()
        ksparser = FilterKickstartParser(handler, valid_sections)

        # Basic test
        kickstart = self._kickstart_include
        self._check_kickstart(ksparser,
                              kickstart = kickstart,
                              commands = ["network", "firewall"],
                              sections = ["%packages", "%post", "%pre", "%addon"])

        # Empty commands and sections
        result = self._check_kickstart(ksparser,
                                       kickstart = kickstart,
                                       commands = [],
                                       sections = [])
        self.assertEqual(result, [])

        # Passing commands in sections and sections in commands !?
        result = self._check_kickstart(ksparser,
                                      kickstart = kickstart,
                                      commands = ["%packages"],
                                      sections = ["network"])
        # The result should be empty
        self.assertEqual(result, [])

    def kickstart_from_result_test(self):
        valid_sections = ["%pre", "%pre-install", "%post", "%onerror", "%traceback", "%packages", "%addon", "%anaconda"]
        handler = returnClassForVersion()
        ksparser = FilterKickstartParser(handler, valid_sections)

        kickstart = self._kickstart_include
        result = self._check_kickstart(ksparser,
                             kickstart = kickstart,
                             commands = ["network", "firewall"],
                             sections = ["%packages", "%post", "%pre", "%addon"])
        self.assertEqual(ksparser.kickstart_from_result(result), kickstart_include_result_kickstart)

    def order_of_arguments_test(self):
        valid_sections = ["%pre", "%pre-install", "%post", "%onerror", "%traceback", "%packages", "%addon", "%anaconda"]
        handler = returnClassForVersion()
        ksparser = FilterKickstartParser(handler, valid_sections)
        kickstart = self._kickstart_include
        result1 = self._check_kickstart(ksparser,
                                       kickstart = kickstart,
                                       commands = ["network", "firewall"],
                                       sections = ["%packages", "%post"])
        result2 = self._check_kickstart(ksparser,
                                       kickstart = kickstart,
                                       commands = ["firewall", "network"],
                                       sections = ["%post", "%packages"])
        self.assertEqual(result1, result2)

    def filter_from_string_test(self):
        valid_sections = ["%pre", "%pre-install", "%post", "%onerror", "%traceback", "%packages", "%addon", "%anaconda"]
        handler = returnClassForVersion()
        ksparser = FilterKickstartParser(handler, valid_sections)
        kickstart = self._kickstart_flat

        # Basic test
        result1 = self._check_kickstart_from_string(ksparser,
                                         kickstart = kickstart,
                                         commands = ["network", "firewall"],
                                         sections = ["%packages", "%post", "%pre", "%addon"])
        # Reusing ksparser instance works
        result2 = self._check_kickstart_from_string(ksparser,
                                         kickstart = kickstart,
                                         commands = ["lang", "keyboard"],
                                         sections = ["%pre"])
        self.assertNotEqual(result1, result2)
        result3 = self._check_kickstart_from_string(ksparser,
                                         kickstart = kickstart,
                                         commands = ["network", "firewall"],
                                         sections = ["%packages", "%post", "%pre", "%addon"])
        self.assertEqual(result1, result3)

    def filter_from_string_filename_test(self):
        valid_sections = ["%pre", "%pre-install", "%post", "%onerror", "%traceback", "%packages", "%addon", "%anaconda"]
        handler = returnClassForVersion()
        ksparser = FilterKickstartParser(handler, valid_sections)
        kickstart = self._kickstart_flat

        commands = ["network", "firewall"]
        sections = ["%packages", "%post"]
        filename, content = kickstart[0]

        # Kickstart from string has "<MAIN>" as filename
        result = ksparser.filter_from_string(content, commands, sections)
        for element in result:
            self.assertEqual(element.filename, FilterKickstartParser.unknown_filename)
        # Or the value supplied by filename optional argument
        result = ksparser.filter_from_string(content, commands, sections, filename = filename)
        for element in result:
            self.assertEqual(element.filename, filename)

    def valid_sections_test(self):
        valid_sections = ["%pre", "%pre-install", "%post", "%onerror", "%traceback", "%packages", "%addon", "%anaconda"]
        handler = returnClassForVersion()
        ksparser = FilterKickstartParser(handler, valid_sections)
        kickstart = self._kickstart_flat

        returned_valid_sections = ksparser.valid_sections
        # valid_sections returns new list, not a reference to the internal object
        returned_valid_sections.append("%test")
        self.assertNotEqual(returned_valid_sections, ksparser.valid_sections)

        ksparser.valid_sections = ["%packages"]
        # Invalid section raises exception
        self.assertRaises(KickstartParseError, self._check_kickstart_from_string, ksparser,
                                         kickstart = kickstart,
                                         commands = ["network", "firewall"],
                                         sections = ["%packages", "%post"])
        # setting valid sections back to the original, the exception is gone
        ksparser.valid_sections = valid_sections
        self._check_kickstart_from_string(ksparser,
                                         kickstart = kickstart,
                                         commands = ["network", "firewall"],
                                         sections = ["%packages", "%post"])

    def invalid_command_test(self):
        # Invalid command or command option in kickstart does not raise
        # KickstartParseError because commands and not parsed in the filter.
        ks_content_invalid_command = """
network --device=ens3 --activate
netork --device=ens5 --activate
network --device=ens7 --activate
network --devce=ens9 --activate
""".strip()

        kickstart = [(None, ks_content_invalid_command)]
        handler = returnClassForVersion()
        ksparser = FilterKickstartParser(handler)
        result1 = self._check_kickstart_from_string(ksparser,
                                       kickstart = kickstart,
                                       commands = ["network", "firewall"])
        self.assertEqual(len(result1), 3)
        # It is even possible to filter unknown commands
        result1 = self._check_kickstart_from_string(ksparser,
                                       kickstart = kickstart,
                                       commands = ["netork"])
        self.assertEqual(len(result1), 1)

    def conflicting_commands_test(self):
        # Conflicting commands in kickstart do not raise KickstartParseError
        # because commands are not parsed in the filter.
        ks_content_conflicting_commands = """
# Partitioning conflicts with autopart
part /boot --fstype=xfs --onpart=vda1
part pv.100000 --size=18436 --ondisk=vda
volgroup Vol00 --pesize=4096 pv.100000
logvol / --fstype=xfs --name=lv_root --vgname=Vol00 --size=15360
logvol /home --fstype=xfs --name=lv_home --vgname=Vol00 --size=1024
logvol swap --fstype=swap --name=lv_swap --vgname=Vol00 --size=2048

autopart --encrypted --passphrase=starost --type=lvm
""".strip()
        kickstart = [(None, ks_content_conflicting_commands)]
        handler = returnClassForVersion()
        ksparser = FilterKickstartParser(handler)
        result1 = self._check_kickstart_from_string(ksparser,
                                       kickstart = kickstart,
                                       commands = ["autopart", "part"])
        self.assertEqual(len(result1), 3)

    def missing_include_test(self):
        # Reaction to missing include can be configured in constructor
        ks_content_missing_include = """
network --device=ens3
%include missing_include.cfg
""".strip()
        kickstart = [(None, ks_content_missing_include)]
        handler = returnClassForVersion()
        # By default raises error
        ksparser = FilterKickstartParser(handler)
        self.assertRaises(KickstartError, self._check_kickstart_from_string,
                          ksparser, kickstart = kickstart, commands = ["network"])
        # But can be configured not to
        ksparser = FilterKickstartParser(handler, missing_include_is_fatal=False)
        self._check_kickstart_from_string(ksparser, kickstart = kickstart, commands = ["network"])

