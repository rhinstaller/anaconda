# Containers for working with kickstart elements
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
from enum import Enum


class KickstartElement:
    """Stores element parsed from kickstart with reference to file.

    Element can be a command, a section or an addon. Addon is not considered
    as a section. The type is infered from args argument.
    """

    class KickstartElementType(Enum):
        COMMAND = "command"
        SECTION = "section"
        ADDON = "addon"

    def __init__(self, args, lines, lineno, filename):
        """Construct the element from data obtained by a KickstartParser.

        :param args: tokens parsed from a line by shlex in KickstartParser.
                     - for command the whole command
                     - for section its header
                     - for addon its header
        :type args: list(str)
        :param lines: lines parsed by KickstarParser
                     - for command the whole command
                     - for section its body
                     - for addons its body
        :type lines: list(str)
        :param lineno: reference to command, section header or addon header line
                       in kickstart file
        :type lineno: int
        :param filename: reference to a kickstart file
        :type filename: str
        """
        self._type = self._get_type(args)
        self._args = args
        self._lines = lines
        self._lineno = lineno
        self._filename = filename

        self._name = self._get_name(args)
        self._content = self._get_content(args, lines)

    @property
    def name(self):
        """Name of the element."""
        return self._name

    @property
    def content(self):
        """Full kickstart content of the element."""
        return self._content

    @property
    def lineno(self):
        """Kickstart file line number."""
        return self._lineno

    @property
    def filename(self):
        """Kickstart file name."""
        return self._filename

    @property
    def number_of_lines(self):
        """Returns number of kickstart lines of the element."""
        return self.content.count('\n')

    def is_command(self):
        """The element is a command."""
        return self._type == self.KickstartElementType.COMMAND

    def is_section(self):
        """The element is a section.

        Addon is not considered a section.
        """
        return self._type == self.KickstartElementType.SECTION

    def is_addon(self):
        """The element is an addon."""
        return self._type == self.KickstartElementType.ADDON

    def __repr__(self):
        return "KickstartElement(args={}, lines={}, lineno={}, filename={})".format(
            self._args, self._lines, self._lineno, self._filename)

    def __str__(self):
        return self.content

    def _get_type(self, args):
        e_type = self.KickstartElementType.COMMAND
        if args[0] == "%addon":
            e_type = self.KickstartElementType.ADDON
        elif args[0].startswith("%"):
            e_type = self.KickstartElementType.SECTION
        return e_type

    def _get_name(self, args):
        name = ""
        if self._type == self.KickstartElementType.COMMAND:
            name = args[0]
        elif self._type == self.KickstartElementType.ADDON:
            try:
                name = args[1]
            except IndexError:
                name = ""
        elif self._type == self.KickstartElementType.SECTION:
            name = args[0][1:]
        return name

    def _get_content(self, args, lines):
        content = ""
        if self._type == self.KickstartElementType.COMMAND:
            content = lines[0]
        elif self._type in (self.KickstartElementType.ADDON,
                            self.KickstartElementType.SECTION):
            body = "".join(self._lines)
            if body:
                content = "{}\n{}%end\n".format(" ".join(self._args), body)
            else:
                content = "{}\n%end\n".format(" ".join(self._args))
        return content


class KickstartElements:
    """Container for storing and filtering KickstartElement objects

    Preserves order of added elements.
    """

    def __init__(self):
        self._elements = []

    def append(self, element):
        """Appends KickstartElement to the container.

        :param element: element object to be appended to the container
        :type name: KickstartElement
        """
        self._elements.append(element)

    @property
    def all_elements(self):
        """List of all elements in the container.

        :return: list of all elements in the container
        :rtype: list(KickstartElement)
        """

        return list(self._elements)

    def get_elements(self, commands=None, sections=None, addons=None):
        """Returns selected elements.

        :param commands: names of commands to be returned
        :type commands: list
        :param sections: names of sections to be returned
        :type sections: list
        :param addons: names of addons to be returned
        :type addons: list

        :return: list of filtered elements
        :rtype: list(KickstartElement)
        """

        filtered_elements = []
        for element in self._elements:
            if element.is_command():
                if commands and element.name in commands:
                    filtered_elements.append(element)
            elif element.is_addon():
                if addons and element.name in addons:
                    filtered_elements.append(element)
            elif element.is_section():
                if sections and element.name in sections:
                    filtered_elements.append(element)
        return filtered_elements

    @staticmethod
    def get_kickstart_from_elements(elements=None):
        """Returns kickstart generated from elements.

        :param elements: list of kickstart elements for generated kickstart
        :type elements: list(KickstartElement)

        :return: kickstart
        :rtype: str
        """
        return "".join(element.content for element in elements)

    def __str__(self):
        return str(self._elements)

    @staticmethod
    def get_references_from_elements(elements=None):
        """Returns elements' references to kickstart file.

        :param elements: list of kickstart elements to get references from
        :type elements: list(KickstartElement)

        :return: list of (lineno, file name) element references indexed by
                 line in kickstart given by the elements
        :rtype: list((int, str))
        """
        refs = [(0, "")]
        for element in elements:
            element_refs = element.number_of_lines * [(element.lineno, element.filename)]
            refs.extend(element_refs)
        return refs


class TrackedKickstartElements(KickstartElements):
    """Container for kickstart elements with tracking."""
    def __init__(self):
        super().__init__()
        self._processed_elements = set()

    def get_and_process_elements(self, commands=None, sections=None, addons=None):
        """Returns selected elements and marks them as processed.

        :param commands: names of commands to be returned
        :type commands: list
        :param sections: names of sections to be returned
        :type sections: list
        :param addons: names of addons to be returned
        :type addons: list

        :return: list of filtered elements
        :rtype: list(KickstartElement)
        """
        elements = self.get_elements(commands, sections, addons)
        self._processed_elements.update(elements)
        return elements

    @property
    def unprocessed_elements(self):
        """List of all elements not tracked as processed.

        :return: list of all elements not tracked as processed
        :rtype: list(KickstartElement)
        """
        return [element for element in self._elements
                if element not in self._processed_elements]
