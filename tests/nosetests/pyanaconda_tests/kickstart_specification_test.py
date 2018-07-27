#
# Copyright (C) 2018  Red Hat, Inc.
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
# Red Hat Author(s): Vendula Poncova <vponcova@redhat.com>
#
import unittest
from textwrap import dedent

from pykickstart.errors import KickstartParseError
from pykickstart.commands.skipx import FC3_SkipX
from pykickstart.commands.user import F24_User, F19_UserData
from pykickstart.parser import Packages
from pykickstart.sections import PackageSection

from pyanaconda import kickstart
from pyanaconda.core.kickstart.specification import KickstartSpecification,\
    KickstartSpecificationHandler, KickstartSpecificationParser
from pyanaconda.modules.localization.kickstart import LocalizationKickstartSpecification
from pyanaconda.modules.network.kickstart import NetworkKickstartSpecification
from pyanaconda.modules.payload.kickstart import PayloadKickstartSpecification
from pyanaconda.modules.security.kickstart import SecurityKickstartSpecification
from pyanaconda.modules.services.kickstart import ServicesKickstartSpecification
from pyanaconda.modules.storage.kickstart import StorageKickstartSpecification
from pyanaconda.modules.timezone.kickstart import TimezoneKickstartSpecification
from pyanaconda.modules.users.kickstart import UsersKickstartSpecification


class KickstartSpecificationTestCase(unittest.TestCase):
    """Test the kickstart specification class."""

    class SpecificationA(KickstartSpecification):
        pass

    class SpecificationB(KickstartSpecification):

        commands = {
            "skipx": FC3_SkipX,
        }

    class SpecificationC(KickstartSpecification):

        commands = {
            "user": F24_User,
        }

        commands_data = {
            "UserData": F19_UserData,
        }

    class SpecificationD(KickstartSpecification):

        sections = {
            "packages": PackageSection
        }

        sections_data = {
            "packages": Packages
        }

    class SpecificationE(KickstartSpecification):

        commands = {
            "user": F24_User,
            "skipx": FC3_SkipX,
        }

        commands_data = {
            "UserData": F19_UserData,
        }

        sections = {
            "packages": PackageSection
        }

        sections_data = {
            "packages": Packages
        }

    def parse_kickstart(self, specification, kickstart_input):
        """Parse a kickstart string using the given specification."""
        handler = KickstartSpecificationHandler(specification)
        parser = KickstartSpecificationParser(handler, specification)
        parser.readKickstartFromString(kickstart_input)
        return handler

    def empty_specification_test(self):
        """Test an empty specification."""
        specification = self.SpecificationA
        self.parse_kickstart(specification, "")

        with self.assertRaises(KickstartParseError):
            self.parse_kickstart(specification, "skipx")

    def command_specification_test(self):
        """Test a specification with a command."""
        specification = self.SpecificationB
        self.parse_kickstart(specification, "")
        self.parse_kickstart(specification, "skipx")

        with self.assertRaises(KickstartParseError):
            self.parse_kickstart(specification, "xconfig")

    def command_with_data_specification_test(self):
        """Test a specification with a command and a data."""
        specification = self.SpecificationC
        self.parse_kickstart(specification, "")
        self.parse_kickstart(specification, "user --name John")

        with self.assertRaises(KickstartParseError):
            self.parse_kickstart(specification, "xconfig")

    def section_specification_test(self):
        """Test a specification with a section."""
        specification = self.SpecificationD

        self.parse_kickstart(specification, "")
        self.parse_kickstart(specification, "%packages\n%end")
        self.parse_kickstart(specification, "%packages\na\nb\nc\n%end")

        with self.assertRaises(KickstartParseError):
            self.parse_kickstart(specification, "xconfig")

    def full_specification_test(self):
        """Test a full specification."""
        specification = self.SpecificationE

        self.parse_kickstart(specification, "")
        self.parse_kickstart(specification, "skipx")
        self.parse_kickstart(specification, "user --name John")
        self.parse_kickstart(specification, "%packages\na\nb\nc\n%end")
        self.parse_kickstart(specification, dedent("""
        user --name John
        skipx

        %packages
        x
        y
        z
        %end
        """))

        with self.assertRaises(KickstartParseError):
            self.parse_kickstart(specification, "xconfig")


class ModuleSpecificationsTestCase(unittest.TestCase):
    """Test the kickstart module specifications."""

    SPECIFICATIONS = [
        LocalizationKickstartSpecification,
        NetworkKickstartSpecification,
        PayloadKickstartSpecification,
        SecurityKickstartSpecification,
        ServicesKickstartSpecification,
        StorageKickstartSpecification,
        TimezoneKickstartSpecification,
        UsersKickstartSpecification,
    ]

    def setUp(self):
        pykickstart_handler = kickstart.superclass
        self.pykickstart_commands = pykickstart_handler.commandMap
        self.pykickstart_commands_data = pykickstart_handler.dataMap

    def assert_compare_versions(self, children, parents):
        """Check if children inherit from parents."""
        for name in children:
            print("Checking command {}...".format(name))
            self.assertIsInstance(children[name](), parents[name])

    def version_test(self):
        """Check versions of kickstart commands and data objects."""
        for specification in self.SPECIFICATIONS:
            print("Checking specification {}...".format(specification.__name__))

            self.assert_compare_versions(specification.commands,
                                         self.pykickstart_commands)

            self.assert_compare_versions(specification.commands_data,
                                         self.pykickstart_commands_data)

    def disjoint_commands_test(self):
        """Check if the commands are specified at most once."""
        specified = set()

        for specification in self.SPECIFICATIONS:
            print("Checking specification {}...".format(specification.__name__))

            for obj in specification.commands:
                if obj in specified:
                    self.fail("Command {} is specified more then once!".format(obj))

                specified.add(obj)

    def disjoint_commands_data_test(self):
        """Check if the commands data are specified at most once."""
        specified = set()

        for specification in self.SPECIFICATIONS:
            print("Checking specification {}...".format(specification.__name__))

            for obj in specification.commands_data:
                if obj in specified:
                    self.fail("Data object {} is specified more then once!".format(obj))

                specified.add(obj)

    def disjoint_sections_test(self):
        """Check if the sections are specified at most once."""
        specified = set()

        for specification in self.SPECIFICATIONS:
            print("Checking specification {}...".format(specification.__name__))

            for obj in specification.sections:
                if obj in specified:
                    self.fail("Section {} is specified more then once!".format(obj))

                specified.add(obj)

    def handler_test(self):
        """Check the specification handler."""
        for specification in self.SPECIFICATIONS:
            print("Checking specification {}...".format(specification.__name__))

            # Create the kickstart handler.
            handler = KickstartSpecificationHandler(specification)

            # Test if the handler provides the required data objects.
            for command in specification.commands:
                getattr(handler.commands[command], "dataClass")

    def parser_test(self):
        """Check the specification parser."""
        for specification in self.SPECIFICATIONS:
            print("Checking specification {}...".format(specification.__name__))

            # Create the kickstart parser.
            handler = KickstartSpecificationHandler(specification)
            parser = KickstartSpecificationParser(handler, specification)

            # Read an empty string.
            parser.readKickstartFromString("")
