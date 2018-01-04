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

__all__ = ["SplitKickstartParser", "VALID_SECTIONS_ANACONDA", "KickstartMerger",
           "MergeKickstartUnknownCommandError", "MergeKickstartCommandAlreadyAddedError"]

from pykickstart.parser import KickstartParser
from pykickstart.sections import Section
from pyanaconda.kickstart_dispatcher.element import TrackedKickstartElements, KickstartElement

VALID_SECTIONS_ANACONDA = ["%pre", "%pre-install", "%post", "%onerror", "%traceback",
                           "%packages", "%addon", "%anaconda"]

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
        self._store = kwargs.get("store", None)
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


class MergeKickstartError(Exception):
    """Error while merging kickstart."""
    pass


class MergeKickstartUnknownCommandError(MergeKickstartError):
    """Adding unknown command."""
    def __init__(self, message, command):
        super().__init__(message)
        self.command = command


class MergeKickstartCommandAlreadyAddedError(MergeKickstartError):
    """The command has been already added."""
    def __init__(self, message, command):
        super().__init__(message)
        self.command = command


class KickstartMerger(object):
    """Merges kickstart snippets according to priorities defined by handler.

    The snippets will be merged without any reparsing. They can contain comments
    and should end with a new line character.

    Kickstart commands are ordered according to priorities obtained from
    handler. It is possible to add a snippet for specified command with
    add_command method or a kickstart line containing a command defifiniton
    with add_command_line method.

    For kickstart sections the order of addition is preserved.
    """

    def __init__(self, handler):
        """Initialize the merger with handler as source of priorities.

        :param handler: kickstart handler containing command priorities
        :type handler: BaseHandler
        """

        self._cmd_name_priorities = self._get_cmd_name_priorities(handler)
        self._valid_commands = handler.commands.keys()
        self._added_commands = set()
        self._commands = {}
        self._sections = []

    def _get_cmd_name_priorities(self, handler):
        # Transform the mapping of command objects priorities from handler
        # to a mapping of command names priorities.
        command_names = {}
        for name, cmd in handler.commands.items():
            cmd_class = cmd.__class__.__name__
            if cmd_class in command_names:
                command_names[cmd_class].append(name)
            else:
                command_names[cmd_class] = [name]

        cmd_name_priorities = {}
        for priority, cmds in handler._writeOrder.items():
            cmd_names = []
            for cmd in cmds:
                cmd_names.extend(command_names[cmd.__class__.__name__])
            cmd_name_priorities[priority] = cmd_names
        return cmd_name_priorities

    def add_command(self, command_name, kickstart):
        """Add the kickstart snippet for given command.

        A snippet for a command can be added only once.

        :param command_name: name of the command
        :type command_name: str
        :param kickstart: kickstart snippet for the command
        :type kickstart: str
        :raises MergeKickstartCommandAlreadyAddedError: a snippet for the command
            has already been added
        """
        self._add_command(command_name, kickstart)
        self._added_commands.add(command_name)

    def _add_command(self, command_name, kickstart):
        if command_name not in self._valid_commands:
            raise MergeKickstartUnknownCommandError("Unknown command added.", command_name)
        if command_name in self._added_commands:
            raise MergeKickstartCommandAlreadyAddedError("Command has already been added", command_name)
        if command_name in self._commands:
            self._commands[command_name].append(kickstart)
        else:
            self._commands[command_name] = [kickstart]

    def add_command_line(self, command_line):
        """Add a kickstart line containing a command definition.

        The line won't be added if its command has been already added.

        :param command_line: kickstart command line (including new line)
        :type command_line: str
        :raises MergeKickstartCommandAlreadyAddedError: the command of the
            line has already been added
        """
        command_name = command_line.strip()
        if command_name:
            command_name = command_name.split()[0]
        else:
            command_name = ""

        self._add_command(command_name, command_line)

    def add_section(self, kickstart):
        """Add a snippet containing a kickstart section.

        :param kickstart: kickstart snippet with a section
        :type kickstart: str
        """
        self._sections.append(kickstart)

    def get_kickstart(self):
        """Get merged kickstart.

        :return: kickstart with all added commands and sections merged
        :rtype: str
        """
        snippets = []
        priorities = self._cmd_name_priorities.keys()
        for prio in sorted(priorities):
            for cmd_name in self._cmd_name_priorities[prio]:
                for command_snippet in self._commands.get(cmd_name, []):
                    snippets.append(command_snippet)
        for section in self._sections:
            snippets.append("\n")
            snippets.append(section)
        return "".join(snippets)

    def __str__(self):
        return self.get_kickstart()
