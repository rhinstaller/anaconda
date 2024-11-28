#
# Support for %addon sections.
#
# Copyright (C) 2019  Red Hat, Inc.  All rights reserved.
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
from abc import ABCMeta, abstractmethod
from types import SimpleNamespace

from pykickstart.errors import KickstartParseError
from pykickstart.ko import KickstartObject
from pykickstart.sections import Section

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import _

log = get_module_logger(__name__)

__all__ = ["AddonData", "AddonRegistry", "AddonSection"]


class AddonData(KickstartObject, metaclass=ABCMeta):
    """Kickstart data for addon.

    This is a common parent class for loading and storing 3rd
    party data to kickstart. It is instantiated by kickstart
    parser and stored as ksdata.addons.<name> to be used in
    the user interfaces.

    The following methods have to be implemented:

        * handle_header handles arguments of the section
        * handle_line is called for every line of the section
        * __str__ returns a kickstart representation of the section

    """

    @abstractmethod
    def handle_header(self, args, line_number=None):
        """Handle the arguments of the %addon line.

        This function receives any arguments on the %addon line
        after the name. For example, for the line:

           %addon com_example_foo --argument='example'

        This function would be called with:

            args=["--argument='example'"].

        :param args: a list of additional arguments
        :param line_number: a line number
        :raise: KickstartParseError for invalid arguments
        """
        pass

    @abstractmethod
    def handle_line(self, line, line_number=None):
        """Handle one line of the section.

        :param line: a line to parse
        :param line_number: a line number
        :raise: KickstartParseError for invalid lines
        """
        pass

    def handle_end(self):
        """Handle the end of the section.."""
        pass

    @abstractmethod
    def __str__(self):
        """Generate the kickstart representation.

        Generate the %addon section for your addon.

        For example:

            %addon com_example_foo --argument='example'
            My lines.
            %end

        :return: a string
        """
        return ""


class AddonSection(Section):
    """Parser of the %addon sections.

    Parses the name of the current %addon section and propagates
    all arguments and lines of this section to the addon with the
    specified name.
    """
    sectionOpen = "%addon"

    def __init__(self, handler, **kwargs):
        super().__init__(handler, **kwargs)
        self.data = None
        self.line_number = None

    def handleHeader(self, lineno, args):
        """Handle a header of the current %addon section.

        This method is called when the opening tag for a section is
        seen. Not all sections will need this method, though all
        provided with kickstart include one.

        :param lineno: a number of the current line
        :param args: a list of strings passed as arguments
        """
        super().handleHeader(lineno, args)

        if not args:
            raise KickstartParseError(
                _("Missing name of the %addon section."),
                lineno=lineno
            )

        name = args[1]
        arguments = args[2:]
        data = getattr(self.handler.addons, name, None)

        if not data:
            raise KickstartParseError(
                _("Unknown name of the %addon section."),
                lineno=lineno
            )

        self.data = data
        self.line_number = lineno
        self.data.handle_header(arguments, self.line_number)

    def handleLine(self, line):
        """Handle one line of the current %addon section.

        This method is called for every line of a section. Take
        whatever action is appropriate.  While this method is not
        required to be provided, not providing it does not make
        a whole lot of sense.

        :param line: a complete line, with any trailing newline
        """
        if not self.handler:
            return

        self.line_number += 1
        self.data.handle_line(line, self.line_number)

    def finalize(self):
        """Handle the end of the current %addon section.

        This method is called when the %end tag for a section is
        seen.
        """
        super().finalize()
        self.data.handle_end()
        self.data = None


class AddonRegistry(SimpleNamespace):
    """Data holder of the %addon sections.

    Provides access to instances of AddonData from the handler.

    For example:

        handler.addons.com_example_foo

    """
    pass
