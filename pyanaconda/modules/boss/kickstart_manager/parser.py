# Kickstart parser for splitting kickstart into elements
#
# Copyright (C) 2017  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

__all__ = ["VALID_SECTIONS_ANACONDA", "SplitKickstartParser"]

from pykickstart.parser import KickstartParser
from pykickstart.sections import Section

from pyanaconda.modules.boss.kickstart_manager.element import (
    KickstartElement,
    TrackedKickstartElements,
)

VALID_SECTIONS_ANACONDA = [
    "%certificate", "%pre", "%pre-install", "%post", "%onerror", "%traceback", "%packages",
    "%addon"
]


class StoreSection(Section):
    """Section for storing section content and header line references.

    Similarly as NullSection defines a section that parser will recognize (ie
    will not raise an error). The section will pass itself to an object for storing
    sections if supplied.
    """

    allLines = True

    def __init__(self, *args, **kwargs):
        """Create a new StoreSection instance.

        You must pass a sectionOpen parameter (including a leading '%') for the
        section to make it valid but just ignored. If you want to store the
        content, supply a store argument.

        Required kwargs:
        sectionOpen - section name, including '%' starting character

        Optional kwargs:
        store - an instance of an object for storing the section
                (SplitKickstartParser) which must provide
                add_section(StoreSection) method

        attributes:
        header_lineno - section header line in kickstart file
        args - section header parsed by KickstartParser (shlex)
        lines - list of section body lines
        """
        super().__init__(*args, **kwargs)
        self.sectionOpen = kwargs.get("sectionOpen")
        self._store = kwargs.get("store")
        self.header_lineno = 0
        self.args = []
        self.lines = []

    def handleHeader(self, lineno, args):
        self.header_lineno = lineno
        self.args = args

    def handleLine(self, line):
        self.lines.append(line)

    def finalize(self):
        if self._store is not None:
            self._store.add_section(self)
        self.header_lineno = 0
        self.args = []
        self.lines = []


class SplitKickstartParser(KickstartParser):
    """Kickstart parser for storing kickstart elements.

    Stores kickstart elements (commands, sections, addons) with their line
    number and file name references to kickstart file.
    Does not do any actual command or section parsing (ie command syntax
    checking).

    :raises KickstartParseError: on invalid section
    :raises KickstartError: on missing %include unless instantiated with
                            missing_include_is_fatal=False
    """

    # file name to be used in case of parsing string if not supplied
    unknown_filename = "<MAIN>"

    def __init__(self, handler, valid_sections=None, missing_include_is_fatal=True):
        """Initialize the parser.

        :param valid_sections: list of valid section names (including '%')
        :type valid_sections: list(str)
        :param missing_include_is_fatal: raise KickstartError if included file
                                         is not found
        :type missing_include_is_fatal: bool
        """

        self._valid_sections = valid_sections or []
        # calls setupSections
        super().__init__(handler, missingIncludeIsFatal=missing_include_is_fatal)
        self._current_ks_filename = self.unknown_filename
        self._result = TrackedKickstartElements()

    @property
    def valid_sections(self):
        """List of valid kickstart sections"""
        return list(self._valid_sections)

    @valid_sections.setter
    def valid_sections(self, value):
        self._valid_sections = value

    def split(self, filename):
        """Split the kickstart file into elements.

        :param filename: name of kickstart file
        :type filename: str

        :return: object containing kickstart elements with references to
                 kickstart files
        :rtype: KickstartElements
        """
        with open(filename, "r") as f:
            kickstart = f.read()
        return self.split_from_string(kickstart, filename=filename)

    def split_from_string(self, kickstart, filename=None):
        """Split the kickstart given as string into elements.

        :param kickstart: kickstart to be split
        :type kickstart: str
        :param filename: filename to be used as file reference in the result
        :type filename: str

        :return: object containing kickstart elements with references to
                 kickstart
        :rtype: KickstartElements
        """
        self._reset()
        self._current_ks_filename = filename or self.unknown_filename
        self.readKickstartFromString(kickstart)
        return self._result

    def add_section(self, section):
        """Adds a StoreSection to the result."""
        element = KickstartElement(section.args, section.lines,
                                   section.header_lineno, self._current_ks_filename)
        self._result.append(element)

    def _reset(self):
        self._result = TrackedKickstartElements()
        self.setupSections()

    def _handleInclude(self, f):
        """Overrides parent to keep track of include file names."""
        parent_file = self._current_ks_filename
        self._current_ks_filename = f
        super()._handleInclude(f)
        self._current_ks_filename = parent_file

    def handleCommand(self, lineno, args):
        """Overrides parent method to store the command."""
        element = KickstartElement(args, [self._line], lineno, self._current_ks_filename)
        self._result.append(element)

    def setupSections(self):
        """Overrides parent method to store sections."""
        self._sections = {}
        for section in self._valid_sections:
            self.registerSection(StoreSection(self.handler,
                                              sectionOpen=section,
                                              store=self))
