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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
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
                    value is a class or a tuple (class, section_data_class)
                    where section_data_class is a value to be passed to dataObj
                    class argument (typically the corresponding sections_data class)
    sections_data - mapping of kickstart sections data names to
                    classes that represent them
                    value is a class or a tuple (class, data_list_name)
                    where data_list_name is the name of the attribute holding
                    list of the section data objects of the class
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


class SectionDataListStrWrapper():
    """A wrapper for generating string from a list of kickstart data."""
    def __init__(self, data_list, data):
        """Initializer.

        :param data_list: list of section data objects
        :param data: class required for the object to be included in the string
        """
        self._data_list = data_list
        self._data = data

    def __str__(self):
        retval = []
        for data_obj in self._data_list:
            if isinstance(data_obj, self._data):
                retval.append(data_obj.__str__())
        return "".join(retval)


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
        if isinstance(data, tuple):
            # Multiple data objects (section instances) stored in a list
            data, data_list_name = data
            data_list = []
            setattr(self, data_list_name, data_list)
            obj = SectionDataListStrWrapper(data_list, data)
        else:
            # Single data object for all section instances
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
            if isinstance(section, tuple):
                section_cls, data_obj = section
                self.registerSection(section_cls(handler, dataObj=data_obj))
            else:
                self.registerSection(section(handler))

        if specification.addons:
            self.registerSection(AddonSection(handler))

    def setupSections(self):
        """Do not setup any default sections."""
        pass
