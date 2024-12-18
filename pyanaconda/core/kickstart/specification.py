#
# Base kickstart objects for Anaconda modules.
#
# Copyright (C) 2017 Red Hat, Inc.
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
from pykickstart.base import KickstartHandler
from pykickstart.parser import KickstartParser

from pyanaconda.core.kickstart.addon import AddonRegistry, AddonSection
from pyanaconda.core.kickstart.version import VERSION

__all__ = [
    "KickstartSpecification",
    "KickstartSpecificationHandler",
    "KickstartSpecificationParser",
    "NoKickstartSpecification",
]


class KickstartSpecification:
    """Specification of kickstart data.

    This specification can be used to get the corresponding
    handler and parser to parse and handle kickstart data
    described by this specification.

    You should call get_kickstart_handler to get the kickstart
    handler for this specification.

    You should call get_kickstart_parser to get the kickstart
    parser for this specification.

    A specification is defined by these attributes:

    version       - version of this specification
    commands      - mapping of kickstart command names to
                    classes that represent them
    commands_data - mapping of kickstart data names to
                    classes that represent them
    sections      - mapping of kickstart sections names to
                    classes that represent them
    sections_data - mapping of kickstart sections data names to
                    classes that represent them
    addons        - mapping of kickstart addons names to
                    classes that represent them

    """

    version = VERSION
    commands = {}
    commands_data = {}
    sections = {}
    sections_data = {}
    addons = {}


class NoKickstartSpecification(KickstartSpecification):
    """Specification for no kickstart data."""
    pass


class KickstartSpecificationHandler(KickstartHandler):
    """Handler defined by a kickstart specification."""

    def __init__(self, specification):
        super().__init__()
        self.version = specification.version

        for name, command in specification.commands.items():
            self.registerCommand(name, command)

        for name, data in specification.commands_data.items():
            self.registerData(name, data)

        for name, data in specification.sections_data.items():
            self.registerSectionData(name, data)

        if specification.addons:
            self.addons = AddonRegistry()

        for name, data in specification.addons.items():
            self.registerAddonData(name, data)

        self.scripts = []

    def registerSectionData(self, name, data):
        """Register data used by a section."""
        obj = data()
        setattr(self, name, obj)
        self._registerWriteOrder(obj)

    def registerAddonData(self, name, data):
        """Register data used by %addon."""
        obj = data()
        setattr(self.addons, name, obj)
        self._registerWriteOrder(obj)

    def _registerWriteOrder(self, obj):
        """Write the object at the end of the output."""
        write_priority = 0

        if self._writeOrder:
            write_priority = max(self._writeOrder.keys()) + 100

        self._writeOrder[write_priority] = [obj]


class KickstartSpecificationParser(KickstartParser):
    """Parser defined by a kickstart specification."""

    def __init__(self, handler, specification):
        super().__init__(handler)

        for section in specification.sections.values():
            self.registerSection(section(handler))

        if specification.addons:
            self.registerSection(AddonSection(handler))

    def setupSections(self):
        """Do not setup any default sections."""
        pass
