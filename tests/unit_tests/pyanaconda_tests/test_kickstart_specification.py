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
import pytest
import warnings

from textwrap import dedent

from pykickstart.base import RemovedCommand
from pykickstart.errors import KickstartParseError
from pykickstart.commands.skipx import FC3_SkipX
from pykickstart.commands.user import F24_User, F19_UserData
from pykickstart.options import KSOptionParser
from pykickstart.parser import Packages, Certificate
from pykickstart.sections import PackageSection, CertificateSection
from pykickstart.version import F30

from pyanaconda import kickstart
from pyanaconda.core.kickstart.addon import AddonData, AddonRegistry
from pyanaconda.core.kickstart.specification import KickstartSpecification,\
    KickstartSpecificationHandler, KickstartSpecificationParser
from pyanaconda.kickstart import AnacondaKickstartSpecification
from pyanaconda.modules.localization.kickstart import LocalizationKickstartSpecification
from pyanaconda.modules.network.kickstart import NetworkKickstartSpecification
from pyanaconda.modules.payloads.kickstart import PayloadKickstartSpecification
from pyanaconda.modules.security.kickstart import SecurityKickstartSpecification
from pyanaconda.modules.services.kickstart import ServicesKickstartSpecification
from pyanaconda.modules.storage.kickstart import StorageKickstartSpecification
from pyanaconda.modules.subscription.kickstart import SubscriptionKickstartSpecification
from pyanaconda.modules.timezone.kickstart import TimezoneKickstartSpecification
from pyanaconda.modules.users.kickstart import UsersKickstartSpecification


class TestData1(AddonData):

    def __init__(self):
        super().__init__()
        self.seen = False
        self.foo = None
        self.bar = False
        self.lines = []

    def handle_header(self, args, line_number=None):
        # Create the argument parser.
        op = KSOptionParser(
            prog="%addon my_test_1",
            version=F30,
            description="My addon test 1."
        )

        op.add_argument(
            "--foo",
            type=int,
            default=None,
            version=F30,
            help="Specify foo."
        )

        op.add_argument(
            "--bar",
            action="store_true",
            default=False,
            version=F30,
            help="Specify bar."
        )

        # Parse the arguments.
        ns = op.parse_args(args=args, lineno=line_number)

        # Store the result of the parsing.
        self.seen = True
        self.foo = ns.foo
        self.bar = ns.bar

    def handle_line(self, line, line_number=None):
        self.lines.append(line.strip())

    def __str__(self):
        if not self.seen:
            return ""

        section = "\n%addon my_test_1"

        if self.foo is not None:
            section += " --foo={}".format(self.foo)

        if self.bar:
            section += " --bar"

        for line in self.lines:
            section += "\n{}".format(line)

        section += "\n%end\n"
        return section


class TestData2(AddonData):

    def __init__(self):
        super().__init__()
        self.seen = False
        self.args = []

    def handle_header(self, args, line_number=None):
        # Create the argument parser.
        op = KSOptionParser(
            prog="%addon my_test_2",
            version=F30,
            description="My addon test 2."
        )

        # Parse the arguments.
        _, extra = op.parse_known_args(args=args, lineno=line_number)

        # Store the result of the parsing.
        self.seen = True
        self.args = extra

    def handle_line(self, line, line_number=None):
        if line:
            raise KickstartParseError(line, line_number)

    def __str__(self):
        if not self.seen:
            return ""

        section = "\n%addon my_test_2"

        for arg in self.args:
            section += " {}".format(arg)

        section += "\n%end\n"
        return section


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

    class SpecificationF(KickstartSpecification):

        addons = {
            "my_test_1": TestData1,
            "my_test_2": TestData2
        }

    class SpecificationG(KickstartSpecification):

        sections = {
            "certificate": CertificateSection,
        }

        sections_data = {
            "certificate": Certificate,
        }

    def setUp(self):
        self.maxDiff = None

    def parse_kickstart(self, specification, kickstart_input, kickstart_output=None):
        """Parse a kickstart string using the given specification."""
        handler = KickstartSpecificationHandler(specification)
        parser = KickstartSpecificationParser(handler, specification)
        parser.readKickstartFromString(dedent(kickstart_input))

        if kickstart_output is not None:
            assert str(handler).strip() == dedent(kickstart_output).strip()

        return handler

    def test_empty_specification(self):
        """Test an empty specification."""
        specification = self.SpecificationA
        self.parse_kickstart(specification, "")

        with pytest.raises(KickstartParseError):
            self.parse_kickstart(specification, "skipx")

    def test_command_specification(self):
        """Test a specification with a command."""
        specification = self.SpecificationB
        self.parse_kickstart(specification, "")
        self.parse_kickstart(specification, "skipx")

        with pytest.raises(KickstartParseError):
            self.parse_kickstart(specification, "xconfig")

    def test_command_with_data_specification(self):
        """Test a specification with a command and a data."""
        specification = self.SpecificationC
        self.parse_kickstart(specification, "")
        self.parse_kickstart(specification, "user --name John")

        with pytest.raises(KickstartParseError):
            self.parse_kickstart(specification, "xconfig")

    def test_section_specification(self):
        """Test a specification with a section."""
        specification = self.SpecificationD

        self.parse_kickstart(specification, "")
        self.parse_kickstart(specification, "%packages\n%end")
        self.parse_kickstart(specification, "%packages\na\nb\nc\n%end")

        with pytest.raises(KickstartParseError):
            self.parse_kickstart(specification, "xconfig")

    def test_full_specification(self):
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

        with pytest.raises(KickstartParseError):
            self.parse_kickstart(specification, "xconfig")

    def test_first_addon_specification(self):
        specification = self.SpecificationF

        ks_in = """
        %addon my_test_1
        %end
        """
        ks_out = """
        %addon my_test_1
        %end
        """
        handler = self.parse_kickstart(specification, ks_in, ks_out)
        assert handler.addons.my_test_1.foo is None
        assert handler.addons.my_test_1.bar is False
        assert handler.addons.my_test_1.lines == []

        ks_in = """
        %addon my_test_1 --foo=10 --bar
        1
        2
        3
        %end
        """
        ks_out = """
        %addon my_test_1 --foo=10 --bar
        1
        2
        3
        %end
        """
        handler = self.parse_kickstart(specification, ks_in, ks_out)
        assert handler.addons.my_test_1.foo == 10
        assert handler.addons.my_test_1.bar is True
        assert handler.addons.my_test_1.lines == ["1", "2", "3"]

        with pytest.raises(KickstartParseError):
            self.parse_kickstart(specification, """
            %addon my_test_1 --invalid-arg
            %end
            """)

    def test_second_addon_specification(self):
        specification = self.SpecificationF

        ks_in = """
        %addon my_test_2
        %end
        """
        ks_out = """
        %addon my_test_2
        %end
        """
        handler = self.parse_kickstart(specification, ks_in, ks_out)
        assert handler.addons.my_test_2.args == []

        ks_in = """
        %addon my_test_2 --arg1 --arg2 --arg3
        %end
        """
        ks_out = """
        %addon my_test_2 --arg1 --arg2 --arg3
        %end
        """
        handler = self.parse_kickstart(specification, ks_in, ks_out)
        assert handler.addons.my_test_2.args == ["--arg1", "--arg2", "--arg3"]

        with pytest.raises(KickstartParseError):
            self.parse_kickstart(specification, """
            %addon my_test_2
            Invalid line!
            %end
            """)

    def test_addons_specification(self):
        specification = self.SpecificationF

        handler = self.parse_kickstart(specification, "", "")
        assert isinstance(handler.addons, AddonRegistry)
        assert isinstance(handler.addons.my_test_1, TestData1)
        assert isinstance(handler.addons.my_test_2, TestData2)

        ks_in = """
        %addon my_test_1 --foo=10 --bar
        Line!
        %end

        %addon my_test_2 --arg1 --arg2
        %end
        """
        ks_out = """
        %addon my_test_1 --foo=10 --bar
        Line!
        %end

        %addon my_test_2 --arg1 --arg2
        %end
        """
        self.parse_kickstart(specification, ks_in, ks_out)

        with pytest.raises(KickstartParseError):
            self.parse_kickstart(specification, """
           %addon my_test_unknown
           %end
           """)

    def test_certificates_specification(self):
        specification = self.SpecificationG

        ks_in = """
        %certificate --filename=cert1.pem
        -----BEGIN CERTIFICATE-----
        MIIDazCCAlOgAwIBAgIJAJzQz1Zz1Zz1MA0GCSqGSIb3DQEBCwUAMIGVMQswCQYD
        -----END CERTIFICATE-----
        %end
        """
        handler = self.parse_kickstart(specification, ks_in)
        assert isinstance(handler.certificates[0], Certificate)
        assert len(handler.certificates) == 1


class ModuleSpecificationsTestCase(unittest.TestCase):
    """Test the kickstart module specifications."""

    SPECIFICATIONS = [
        AnacondaKickstartSpecification,
        LocalizationKickstartSpecification,
        NetworkKickstartSpecification,
        PayloadKickstartSpecification,
        SecurityKickstartSpecification,
        ServicesKickstartSpecification,
        StorageKickstartSpecification,
        SubscriptionKickstartSpecification,
        TimezoneKickstartSpecification,
        UsersKickstartSpecification,
    ]

    # Names of the kickstart commands and data that should be temporarily ignored.
    IGNORED_NAMES = {
    }

    # Names of shared kickstart commands and data that should be temporarily ignored.
    IGNORED_SHARED_NAMES = {
        "liveimg"
    }

    # Names of possibly missing kickstart commands and data that should be ignored.
    IGNORED_MISSING_NAMES = {
        "rhsm",
        "syspurpose",
    }

    def setUp(self):
        pykickstart_handler = kickstart.superclass
        self.pykickstart_commands = pykickstart_handler.commandMap
        self.pykickstart_commands_data = pykickstart_handler.dataMap

    def assert_compare_versions(self, children, parents):
        """Check if children inherit from parents."""
        for name in children:
            if name in self.IGNORED_NAMES:
                warnings.warn("Skipping the ignored name: {}".format(name))
                continue

            if name not in parents and name in self.IGNORED_MISSING_NAMES:
                warnings.warn("Skipping the missing name: {}".format(name))
                continue

            print("Checking command {}...".format(name))
            assert isinstance(children[name](), parents[name])

    def test_version(self):
        """Check versions of kickstart commands and data objects."""
        for specification in self.SPECIFICATIONS:
            print("Checking specification {}...".format(specification.__name__))

            self.assert_compare_versions(specification.commands,
                                         self.pykickstart_commands)

            self.assert_compare_versions(specification.commands_data,
                                         self.pykickstart_commands_data)

    def test_all_commands(self):
        """Check if we process all kickstart commands."""
        # Collect the specified commands.
        specified = set()

        for specification in self.SPECIFICATIONS:
            specified.update(specification.commands.keys())

        # Collect the expected commands.
        expected = set()

        for name, obj in self.pykickstart_commands.items():
            if issubclass(obj, RemovedCommand):
                continue

            expected.add(name)

        # Ignore specified names if missing.
        for name in self.IGNORED_MISSING_NAMES:
            if name in expected ^ specified:
                warnings.warn("Skipping the missing name: {}".format(name))
                expected.discard(name)
                specified.discard(name)

        # Check the differences.
        assert specified == expected

    def test_disjoint_commands(self):
        """Check if the commands are specified at most once."""
        specified = set()

        for specification in self.SPECIFICATIONS:
            print("Checking specification {}...".format(specification.__name__))

            for name in specification.commands.keys():
                if name in self.IGNORED_SHARED_NAMES:
                    warnings.warn("Skipping the shared name {}.".format(name))
                    continue

                if name in specified:
                    self.fail("Command {} is specified more then once!".format(name))

                specified.add(name)

    def test_disjoint_commands_data(self):
        """Check if the commands data are specified at most once."""
        specified = set()

        for specification in self.SPECIFICATIONS:
            print("Checking specification {}...".format(specification.__name__))

            for name in specification.commands_data.keys():
                if name in specified:
                    self.fail("Data object {} is specified more then once!".format(name))

                specified.add(name)

    def test_disjoint_sections(self):
        """Check if the sections are specified at most once."""
        specified = set()

        for specification in self.SPECIFICATIONS:
            print("Checking specification {}...".format(specification.__name__))

            for name in specification.sections.keys():
                if name in specified:
                    self.fail("Section {} is specified more then once!".format(name))

                specified.add(name)

    def test_handler(self):
        """Check the specification handler."""
        for specification in self.SPECIFICATIONS:
            print("Checking specification {}...".format(specification.__name__))

            # Create the kickstart handler.
            handler = KickstartSpecificationHandler(specification)

            # Test if the handler provides the required data objects.
            for command in specification.commands:
                getattr(handler.commands[command], "dataClass")

    def test_parser(self):
        """Check the specification parser."""
        for specification in self.SPECIFICATIONS:
            print("Checking specification {}...".format(specification.__name__))

            # Create the kickstart parser.
            handler = KickstartSpecificationHandler(specification)
            parser = KickstartSpecificationParser(handler, specification)

            # Read an empty string.
            parser.readKickstartFromString("")

    def test_useless_command_map(self):
        """Check kickstart commands marked as useless."""
        # Get a set of command names that are handled by the main process.
        anaconda_names = AnacondaKickstartSpecification.commands.keys()

        # Get a set of command names that are handled by modules.
        module_names = set()

        for specification in self.SPECIFICATIONS:
            if specification is not AnacondaKickstartSpecification:
                module_names.update(specification.commands.keys())

        # Useless commands has to be handled by modules.
        # Otherwise, they has to be handled by the main process.
        for name, command in kickstart.commandMap.items():
            if issubclass(command, kickstart.UselessCommand):
                assert name in module_names
            else:
                assert name in anaconda_names
