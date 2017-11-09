# Anaconda kickstart dispatching for modules
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

from collections import namedtuple

from pykickstart.parser import KickstartParser
from pykickstart.sections import Section

KickstartCommandOrSection = namedtuple('KickstartCommandOrSection',
                                       ['content', 'lineno', 'filename'])


class FilterSection(Section):
    """Section for storing section content and header line references.

    Similarly as NullSection defines a section that parser will recognize (ie
    will not raise an error) and optionally pass itself to a supplied object
    for storing the section.
    """

    allLines = True

    def __init__(self, *args, **kwargs):
        """Create a new FilterSection instance.

        You must pass a sectionOpen parameter (including a leading '%') for the
        section to make it valid but just ignored. If you want to store the
        content, supply a filter argument.

        Required kwargs:

        sectionOpen - section name, including '%' starting character

        Optional kwargs:
        filter - an instance of filter object for storing the section
                 (KickstartFilterParser) which has to provide add_section(FilterSection)
                 method
        """
        super().__init__(*args, **kwargs)
        self.sectionOpen = kwargs.get("sectionOpen")
        self._filter = kwargs.get("filter", None)
        self.header_lineno = 0
        self._args = []
        self._body = []

    def handleHeader(self, lineno, args):
        self.header_lineno = lineno
        self._args = args

    def handleLine(self, line):
        self._body.append(line)

    def __str__(self):
        body = "".join(self._body)
        if body:
            s = "{}\n{}%end\n".format(" ".join(self._args), body)
        else:
            s = "{}\n%end\n".format(" ".join(self._args))
        return s

    def finalize(self):
        if self._filter is not None:
            self._filter.add_section(self)
        self.header_lineno = 0
        self._args = []
        self._body = []


class FilterKickstartParser(KickstartParser):
    """Kickstart parser for filtering specific commands and sections.

    Filters specified commands and sections. Does not do any actual command
    or section parsing (ie command syntax checking).
    """

    unknown_filename = "<MAIN>"

    def __init__(self, handler, valid_sections=None, missing_include_is_fatal=True):
        """Initialize the filter.

        :param valid_sections: list of valid kickstart sections
        :type valid_sections: list(str)
        :param missing_include_is_fatal: raise error if included file is not found
        :type missing_include_is_fatal: bool
        """

        self._valid_sections = valid_sections or []
        self._accepted_sections = []
        # calls setupSections
        super().__init__(handler, missingIncludeIsFatal=missing_include_is_fatal)
        self._accepted_commands = []
        self._current_ks_filename = self.unknown_filename
        self._result = []

    @property
    def valid_sections(self):
        """List of valid kickstart sections"""
        return list(self._valid_sections)

    @valid_sections.setter
    def valid_sections(self, value):
        self._valid_sections = value

    def filter(self, filename, commands=None, sections=None):
        """Filter commands and sections from kickstart given by filename.

        :param filename: name of kickstart file
        :type filename: str
        :param commands: list of accepted commands
        :type commands: list(str)
        :param sections: list of accepted sections (including % starting character)
        :type sections: list(str)

        :return: List of objects containing filtered commands and sections.
                 For command it contains the line, line number and kickstart filename
                 For section it contains the section, section header line number
                 and kickstart filename.
                 The list preservers the order of commands and sections.
        :rtype: list(KickstartCommandOrSection)
        """
        with open(filename, "r") as f:
            kickstart = f.read()
        return self.filter_from_string(kickstart, commands=commands, sections=sections,
                                       filename=filename)

    def filter_from_string(self, kickstart, commands=None, sections=None, filename=None):
        """Filter commands and sections from kickstart given by string

        :param kickstart: string containing kickstart
        :type kickstart: str
        :param commands: list of accepted commands
        :type commands: list(str)
        :param sections: list of accepted sections (including % starting character)
        :type sections: list(str)
        :param filename: filename to be used as file reference in the result
        :type filename: str

        :return: List of objects containing filtered commands and sections.
                 For command it contains the line, line number and kickstart filename
                 For section it contains the section, section header line number
                 and kickstart filename.
                 The list preserves the order of commands and sections.
        :rtype: list(KickstartCommandOrSection)
        """
        self._reset()
        self._accepted_commands = commands or []
        self._accepted_sections = sections or []
        self._current_ks_filename = filename or self.unknown_filename
        self.readKickstartFromString(kickstart)
        return self._result

    @staticmethod
    def kickstart_from_result(result):
        """Returns kickstart generated from the filtering result."""
        return "".join(element.content for element in result)

    def add_section(self, section):
        """Adds the section instance of FilterSection to result."""
        section = KickstartCommandOrSection(str(section),
                                            section.header_lineno,
                                            self._current_ks_filename)
        self._result.append(section)

    def _reset(self):
        self._result = []
        self.setupSections()

    def _handleInclude(self, f):
        """Overrides parent to keep track of kickstart filename following includes."""
        parent_file = self._current_ks_filename
        self._current_ks_filename = f
        super()._handleInclude(f)
        self._current_ks_filename = parent_file

    def handleCommand(self, lineno, args):
        """Overrides parent method to store filtered command."""
        if args[0] in self._accepted_commands:
            command = KickstartCommandOrSection(self._line, lineno, self._current_ks_filename)
            self._result.append(command)

    def setupSections(self):
        """Overrides parent method to store content of filtered sections."""
        self._sections = {}
        for section in self._valid_sections:
            if section in self._accepted_sections:
                ksfilter = self
            else:
                ksfilter = None
            self.registerSection(FilterSection(self.handler,
                                               sectionOpen=section,
                                               filter=ksfilter))
