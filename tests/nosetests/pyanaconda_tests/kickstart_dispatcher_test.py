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

from pyanaconda.modules.boss.kickstart_manager.element import KickstartElement,\
    TrackedKickstartElements
from pyanaconda.modules.boss.kickstart_manager.parser import SplitKickstartParser
from pykickstart.version import makeVersion
from pykickstart.errors import KickstartParseError, KickstartError

VALID_SECTIONS_ANACONDA = ["%pre", "%pre-install", "%post", "%onerror", "%traceback",
                           "%packages", "%addon", "%anaconda"]

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
@base
%end

%post --nochroot --interpreter /usr/bin/bash

echo "POST1"
%end

%post --nochroot --interpreter /usr/bin/bash
echo "POST2"
%end
""".strip()


# Flat kickstart without %includes
kickstart_flat = [("ks.test.flat.cfg", KICKSTART1.replace("%include {}", ""))]

# Kickstart with
# - 2 levels of %include
# - sections in included kickstart
INCLUDE_LEVEL_1_FILENAME = "ks.test.include1.cfg"
INCLUDE_LEVEL_2_FILENAME = "ks.test.include2.cfg"
kickstart_include = [
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

kickstart_include_output = """
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
network --device=ens51 --activate
repo --name=repo1 --baseurl=http://bla.bla/repo1
network --device=ens541 --activate
%post --nochroot --interpreter /usr/bin/bash
echo "POST_include2"
%end
network --device=ens55 --activate
network --device=ens56 --activate
repo --name=repo1 --baseurl=http://bla.bla/repo1
%packages
@include1
%end
%addon pony --fly=True
%end
bootloader --location=mbr --boot-drive=vda --driveorder=vda
clearpart --all --drives=vda
ignoredisk --only-use=vda
firewall --enabled
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
""".lstrip()

kickstart_empty = [("ks.test.cfg", """
""".lstrip())]
kickstart_empty_output = """
""".lstrip()

kickstart_almost_empty = [("ks.test.cfg", """
#version=DEVEL
""".lstrip())]
kickstart_almost_empty_output = """
""".lstrip()

kickstart_section_without_end = [("ks.test.cfg", """
text
%packages
anaconda
""".lstrip())]

kickstart_invalid_addon = [("ks.test.cfg", """
text
%addon
anaconda
%end
""".lstrip())]
kickstart_invalid_addon_output = """
text
%addon
anaconda
%end
""".lstrip()


class KickstartElementTest(unittest.TestCase):

    def kickstart_element_test(self):
        """Tests creating of element and his type."""

        filename = "ks.cfg"

        # Ordinary command
        element = KickstartElement(["network", "--device=ens3", "--activate"],
                                   ["network --device=ens3 --activate\n"],
                                   4, filename)
        self.assertEqual(element.filename, filename)
        self.assertEqual(element.lineno, 4)
        self.assertEqual(element.name, "network")
        self.assertEqual(element.content, "network --device=ens3 --activate\n")
        self.assertEqual(element.is_command(), True)
        self.assertEqual(element.is_section(), False)
        self.assertEqual(element.is_addon(), False)

        # Ordinary section
        element = KickstartElement(["%post", "--nochroot", "--interpreter", "/usr/bin/bash"],
                                   ["echo POST1\n"],
                                   12, filename)
        self.assertEqual(element.filename, filename)
        self.assertEqual(element.lineno, 12)
        self.assertEqual(element.name, "post")
        self.assertEqual(element.content,
                         "%post --nochroot --interpreter /usr/bin/bash\necho POST1\n%end\n")
        self.assertEqual(element.is_command(), False)
        self.assertEqual(element.is_section(), True)
        self.assertEqual(element.is_addon(), False)

        # Ordinary addon
        element = KickstartElement(["%addon", "scorched", "--planet=Earth"],
                                   ["nuke\n"],
                                   9, filename)
        self.assertEqual(element.filename, filename)
        self.assertEqual(element.lineno, 9)
        self.assertEqual(element.name, "scorched")
        self.assertEqual(element.content, "%addon scorched --planet=Earth\nnuke\n%end\n")
        self.assertEqual(element.is_command(), False)
        # NOTE We do not consider addon being a section
        self.assertEqual(element.is_section(), False)
        self.assertEqual(element.is_addon(), True)

        # Some more special commands

        # no options
        element = KickstartElement(["text"],
                                   ["text\n"],
                                   1, filename)
        self.assertEqual(element.name, "text")
        self.assertEqual(element.content, "text\n")
        self.assertEqual(element.is_command(), True)
        self.assertEqual(element.is_section(), False)
        self.assertEqual(element.is_addon(), False)

        # Some more special sections

        # no args
        element = KickstartElement(["%pre"],
                                   ["echo PRE\n"],
                                   1, filename)
        self.assertEqual(element.name, "pre")
        self.assertEqual(element.content, "%pre\necho PRE\n%end\n")
        self.assertEqual(element.is_command(), False)
        self.assertEqual(element.is_section(), True)
        self.assertEqual(element.is_addon(), False)
        # no body
        element = KickstartElement(["%packages", "--no-core"],
                                   [],
                                   1, filename)
        self.assertEqual(element.name, "packages")
        self.assertEqual(element.content, "%packages --no-core\n%end\n")
        self.assertEqual(element.is_command(), False)
        self.assertEqual(element.is_section(), True)
        self.assertEqual(element.is_addon(), False)

        # Some more special addons

        # no body
        element = KickstartElement(["%addon", "pony", "--fly=True"],
                                   [],
                                   1, filename)
        self.assertEqual(element.name, "pony")
        self.assertEqual(element.content, "%addon pony --fly=True\n%end\n")
        self.assertEqual(element.is_command(), False)
        self.assertEqual(element.is_section(), False)
        self.assertEqual(element.is_addon(), True)
        # no name! - we don't fail
        element = KickstartElement(["%addon"],
                                   ["blah\n"],
                                   1, filename)
        self.assertEqual(element.name, "")
        self.assertEqual(element.content, "%addon\nblah\n%end\n")
        self.assertEqual(element.is_command(), False)
        self.assertEqual(element.is_section(), False)
        self.assertEqual(element.is_addon(), True)


class TrackedKickstartElementsTest(unittest.TestCase):

    def setUp(self):
        self._expected_ks_content = """
%pre
echo PRE
%end
network --device=ens3 --activate
network --device=ens4 --activate
%addon pony --fly=True
%end
firewall --enabled
%addon scorched --planet=Earth
nuke
%end
%post --nochroot --interpreter /usr/bin/bash
echo POST1
%end
""".lstrip()

        filename = "ks.test.simple.cfg"
        self._element1 = KickstartElement(["%pre"],
                                          ["echo PRE\n"],
                                          1, filename)
        self._element2 = KickstartElement(["network", "--device=ens3", "--activate"],
                                          ["network --device=ens3 --activate\n"],
                                          4, filename)
        self._element3 = KickstartElement(["network", "--device=ens4", "--activate"],
                                          ["network --device=ens4 --activate\n"],
                                          5, filename)
        self._element4 = KickstartElement(["%addon", "pony", "--fly=True"],
                                          [],
                                          6, filename)
        self._element5 = KickstartElement(["firewall", "--enabled"],
                                          ["firewall --enabled\n"],
                                          8, filename)
        self._element6 = KickstartElement(["%addon", "scorched", "--planet=Earth"],
                                          ["nuke\n"],
                                          9, filename)
        self._element7 = KickstartElement(["%post", "--nochroot", "--interpreter",
                                           "/usr/bin/bash"],
                                          ["echo POST1\n"],
                                          12, filename)

        self._expected_element_refs = [
            (0, ""),
            (1, filename),
            (1, filename),
            (1, filename),
            (4, filename),
            (5, filename),
            (6, filename),
            (6, filename),
            (8, filename),
            (9, filename),
            (9, filename),
            (9, filename),
            (12, filename),
            (12, filename),
            (12, filename),
        ]

    def tracked_kickstart_elements_filter_test(self):
        """Test filtering of elements."""

        expected_elements = [self._element1, self._element2, self._element3,
                             self._element4, self._element5, self._element6,
                             self._element7]
        elements = TrackedKickstartElements()
        for element in expected_elements:
            elements.append(element)

        self.assertEqual(elements.all_elements, expected_elements)

        # filtering
        network_commands = elements.get_elements(commands=["network"])
        self.assertEqual(network_commands, [self._element2, self._element3])

        pony_addon = elements.get_elements(addons=["pony"])
        self.assertEqual(pony_addon, [self._element4])

        pre_sections = elements.get_elements(sections=["pre"])
        self.assertEqual(pre_sections, [self._element1])
        # addon is not considered a section
        addon_sections = elements.get_elements(sections=["addon"])
        self.assertEqual(addon_sections, [])

        mixed_elements = elements.get_elements(commands=["network"],
                                               sections=["pre", "post"],
                                               addons=["pony"])
        self.assertEqual(mixed_elements,
                         [self._element1, self._element2, self._element3, self._element4,
                          self._element7])

        # nothing required - nothing got
        self.assertEqual(elements.get_elements(), [])

    def tracked_kickstart_elements_tracking_test(self):
        """Test tracking of elements."""

        appended_elements = [self._element1, self._element2, self._element3,
                             self._element4, self._element5, self._element6,
                             self._element7]
        elements = TrackedKickstartElements()
        for element in appended_elements:
            elements.append(element)

        processed_elements = elements.get_and_process_elements(commands=["network"],
                                                               sections=["pre"],
                                                               addons=["pony"])
        unprocessed_elements = elements.unprocessed_elements
        # still keeping order of elements
        self.assertEqual(unprocessed_elements,
                         [self._element5, self._element6, self._element7])
        # nothing is missing
        self.assertEqual(set(elements.all_elements),
                         set.union(set(processed_elements), set(unprocessed_elements)))
        # elements once processed remain processed if you just get them
        elements.get_elements(commands=["network"], sections=["pre"], addons=["pony"])
        self.assertEqual(elements.unprocessed_elements, unprocessed_elements)
        # processing some more elements - firewall command
        firewall_elements = elements.get_and_process_elements(commands=["firewall"])
        self.assertEqual(set(elements.unprocessed_elements),
                         set.difference(set(unprocessed_elements), set(firewall_elements)))
        self.assertEqual(elements.unprocessed_elements, [self._element6, self._element7])

    def tracked_kickstart_elements_dump_kickstart_test(self):
        """Test dumping of elements into kickstart."""

        appended_elements = [self._element1, self._element2, self._element3,
                             self._element4, self._element5, self._element6,
                             self._element7]
        elements = TrackedKickstartElements()
        for element in appended_elements:
            elements.append(element)

        dumped_ks = elements.get_kickstart_from_elements(elements.all_elements)
        self.assertEqual(dumped_ks, self._expected_ks_content)

    def tracked_kickstart_elements_get_refs_kickstart_test(self):
        """Test getting of element references."""

        appended_elements = [self._element1, self._element2, self._element3,
                             self._element4, self._element5, self._element6,
                             self._element7]
        elements = TrackedKickstartElements()
        for element in appended_elements:
            elements.append(element)

        element_refs = elements.get_references_from_elements(elements.all_elements)
        self.assertEqual(element_refs, self._expected_element_refs)


class SplitKickstartParserTest(unittest.TestCase):

    def setUp(self):
        self._kickstart_flat = [kickstart_flat, None]
        self._kickstart_include = [kickstart_include, kickstart_include_output]
        self._kickstart_samples = [
            self._kickstart_flat,
            self._kickstart_include,
            [kickstart_almost_empty, kickstart_almost_empty_output],
            [kickstart_empty, kickstart_empty_output],
            [kickstart_invalid_addon, kickstart_invalid_addon_output],
        ]
        self._flat_kickstarts_raising = [
            kickstart_section_without_end,
        ]

    def simple_split_kickstart_parser_test(self):
        """This test should demonstrate usage and output of the parser."""
        ks_content = """
%pre
echo PRE
%end
network --device=ens3 --activate
network --device=ens4 --activate
%addon pony --fly=True
%end
firewall --enabled
%addon scorched --planet=Earth
nuke
%end
%post --nochroot --interpreter /usr/bin/bash
echo POST1
%end
""".lstrip()

        element1 = ("pre", "%pre\necho PRE\n%end\n", 1)
        element2 = ("network", "network --device=ens3 --activate\n", 4)
        element3 = ("network", "network --device=ens4 --activate\n", 5)
        element4 = ("pony", "%addon pony --fly=True\n%end\n", 6)
        element5 = ("firewall", "firewall --enabled\n", 8)
        element6 = ("scorched", "%addon scorched --planet=Earth\nnuke\n%end\n", 9)
        element7 = ("post", "%post --nochroot --interpreter /usr/bin/bash\necho POST1\n%end\n", 12)
        expected_result = [element1, element2, element3, element4, element5, element6, element7]

        filename = "ks.test.simple.cfg"

        valid_sections = VALID_SECTIONS_ANACONDA

        handler = makeVersion()
        ksparser = SplitKickstartParser(handler, valid_sections)

        # Reading kickstart from file

        with open(filename, "w") as f:
            f.write(ks_content)
        result = ksparser.split(filename)
        os.remove(filename)

        for element, expected in zip(result.all_elements, expected_result):
            self.assertEqual(element.filename, filename)
            self.assertEqual((element.name, element.content, element.lineno), expected)

        self.assertEqual(result.get_kickstart_from_elements(result.all_elements), ks_content)

        # Reading kickstart from string

        filename = ksparser.unknown_filename
        result = ksparser.split_from_string(ks_content)

        for element, expected in zip(result.all_elements, expected_result):
            self.assertEqual(element.filename, filename)
            self.assertEqual((element.name, element.content, element.lineno), expected)

        self.assertEqual(result.get_kickstart_from_elements(result.all_elements), ks_content)

        # Reading kickstart from string supplying filename

        filename = "MY_FILENAME"
        result = ksparser.split_from_string(ks_content, filename=filename)

        for element, expected in zip(result.all_elements, expected_result):
            self.assertEqual(element.filename, filename)
            self.assertEqual((element.name, element.content, element.lineno), expected)

        # Dumping kickstart

        self.assertEqual(result.get_kickstart_from_elements(result.all_elements), ks_content)

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

    def _check_line_file_references(self, result, kickstart):
        """Checks that the line/file references in result are correct.

            Uses shlex (as pykickstart) to parse section headers.
        """
        kickstart_file_lines_map = {}
        for filename, content in kickstart:
            kickstart_file_lines_map[filename] = content.splitlines(keepends=True)

        for element in result.all_elements:
            kickstart_line = kickstart_file_lines_map[element.filename][element.lineno-1]
            if element.is_addon or element.is_section:
                # We keep only references to headers.
                header = element.content.strip().split("\n")[0]
                # Headers are not stored as source lines but go through shlex
                # parsing before we can store them in result.
                self.assertEqual(shlex.split(header), shlex.split(kickstart_line))
            elif element.is_command:
                self.assertEqual(element.content, kickstart_line)

    def _split_kickstart_parser_test(self, ksparser, kickstart_files, expected_output=None):
        with self._create_ks_files(kickstart_files) as filename:
            result1 = ksparser.split(filename)

        # The line and file references are correct
        self._check_line_file_references(result1, kickstart_files)

        result1_kickstart = result1.get_kickstart_from_elements(result1.all_elements)
        if expected_output is not None:
            # Compare with expected output kickstart
            self.assertEqual(result1_kickstart, expected_output)

        # Now do one more pass on resulting (flat) kickstart
        result2 = ksparser.split_from_string(result1_kickstart)
        # the result will be different in most cases because of different references
        # but the kickstart should be the same now
        result2_kickstart = result2.get_kickstart_from_elements(result2.all_elements)
        self.assertEqual(result1_kickstart, result2_kickstart)

    def split_kickstart_parser_test(self):
        """Test splitting and dumping of various kickstart samples."""
        valid_sections = VALID_SECTIONS_ANACONDA
        handler = makeVersion()
        ksparser = SplitKickstartParser(handler, valid_sections)
        for kickstart_files, expected_output in self._kickstart_samples:
            self._split_kickstart_parser_test(ksparser, kickstart_files, expected_output)

    def raising_kickstarts_split_test(self):
        """Test of kickstarts expected to raise KickstartParseError."""
        valid_sections = VALID_SECTIONS_ANACONDA
        handler = makeVersion()
        ksparser = SplitKickstartParser(handler, valid_sections)
        for kickstart_files in self._flat_kickstarts_raising:
            _filename, content = kickstart_files[0]
            self.assertRaises(KickstartParseError, ksparser.split_from_string, content)

    def split_from_string_filename_test(self):
        """Test splitting kickstart supplied by string."""
        valid_sections = VALID_SECTIONS_ANACONDA
        handler = makeVersion()
        ksparser = SplitKickstartParser(handler, valid_sections)

        kickstart_files, _output = self._kickstart_flat
        filename, content = kickstart_files[0]

        # Kickstart from string has "<MAIN>" as filename
        result = ksparser.split_from_string(content)
        for element in result.all_elements:
            self.assertEqual(element.filename, SplitKickstartParser.unknown_filename)
        # Or the value supplied by filename optional argument
        result = ksparser.split_from_string(content, filename=filename)
        for element in result.all_elements:
            self.assertEqual(element.filename, filename)

    def valid_sections_test(self):
        """Test setting of valid sections for the parser."""
        valid_sections = VALID_SECTIONS_ANACONDA
        handler = makeVersion()
        ksparser = SplitKickstartParser(handler, valid_sections)
        kickstart_files, _output = self._kickstart_flat
        _filename, content = kickstart_files[0]

        returned_valid_sections = ksparser.valid_sections
        # valid_sections returns new list, not a reference to the internal object
        returned_valid_sections.append("%test")
        self.assertNotEqual(returned_valid_sections, ksparser.valid_sections)

        ksparser.valid_sections = ["%packages"]
        # Invalid section raises exception
        self.assertRaises(KickstartParseError, ksparser.split_from_string, content)
        # setting valid sections back to the original, the exception is gone
        ksparser.valid_sections = valid_sections
        ksparser.split_from_string(content)

    def invalid_command_test(self):
        """Test invalid command or option in kickstart.

        Invalid command or command option in kickstart does not raise
        KickstartParseError because commands are not parsed in the filter.
        """
        ks_content = """
network --device=ens3 --activate
netork --device=ens5 --activate
network --device=ens7 --activate
network --devce=ens9 --activate
""".strip()

        handler = makeVersion()
        ksparser = SplitKickstartParser(handler)
        result = ksparser.split_from_string(ks_content)
        self.assertEqual(len(result.all_elements), 4)

    def conflicting_commands_test(self):
        """Test conflicting commands in kickstart.

        Conflicting commands in kickstart do not raise KickstartParseError
        because commands are not parsed in the filter.
        """
        ks_content = """
# Partitioning conflicts with autopart
part /boot --fstype=xfs --onpart=vda1
part pv.100000 --size=18436 --ondisk=vda
volgroup Vol00 --pesize=4096 pv.100000
logvol / --fstype=xfs --name=lv_root --vgname=Vol00 --size=15360
logvol /home --fstype=xfs --name=lv_home --vgname=Vol00 --size=1024
logvol swap --fstype=swap --name=lv_swap --vgname=Vol00 --size=2048

autopart --encrypted --passphrase=starost --type=lvm
""".strip()

        handler = makeVersion()
        ksparser = SplitKickstartParser(handler)
        result = ksparser.split_from_string(ks_content)
        self.assertEqual(len(result.all_elements), 7)

    def missing_include_test(self):
        """Test behaviour for missing kickstart include files."""
        ks_content = """
network --device=ens3
%include missing_include.cfg
""".strip()

        handler = makeVersion()
        ksparser = SplitKickstartParser(handler)
        # By default raises error
        self.assertRaises(KickstartError, ksparser.split_from_string, ks_content)
        # But can be configured not to
        ksparser = SplitKickstartParser(handler, missing_include_is_fatal=False)
        ksparser.split_from_string(ks_content)
