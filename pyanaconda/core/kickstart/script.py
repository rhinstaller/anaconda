#
# Support for %pre, %pre-install sections.
#
# Copyright (C) 2024  Red Hat, Inc.  All rights reserved.
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
from pykickstart.errors import KickstartParseError
from pykickstart.sections import Section

from pyanaconda.core.i18n import _

__all__ = ["PreScriptSection", "PreInstallScriptSection"]


class PreScriptSection(Section):
    """Parser of the %pre sections.

    Parses the name of the current %pre section and propagates
    all arguments and lines of this section to the pre with the
    specified name.
    """
    sectionOpen = "%pre"

    def __init__(self, handler, **kwargs):
        super().__init__(handler, **kwargs)
        self.data = None
        self.interp = None
        self.error_on_fail = None
        self.log = None

    def handleHeader(self, lineno, args):
        """Handle a header of the current %pre section.

        This method is called when the opening tag for a section is
        seen. Not all sections will need this method, though all
        provided with kickstart include one.

        :param lineno: a number of the current line
        :param args: a list of strings passed as arguments
        """
        super().handleHeader(lineno, args)

        if not args:
            raise KickstartParseError(
                _("Missing name of the %pre section."),
                lineno=lineno
            )

        name = args[1]
        arguments = args[2:]
        data = getattr(self.handler.pre, name, None)

        if not data:
            raise KickstartParseError(
                _("Unknown name of the %pre section."),
                lineno=lineno
            )

        self.data = data
        self.line_number = lineno
        self.data.handle_header(arguments, self.line_number)

    def handleLine(self, line):
        """Handle one line of the current %pre section.

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
        """Handle the end of the current %pre section.

        This method is called when the %end tag for a section is
        seen.
        """
        super().finalize()
        self.data.handle_end()
        self.data = None


class PreInstallScriptSection(Section):
    """Parser of the %pre-install sections.

    Parses the name of the current %pre-install section and propagates
    all arguments and lines of this section to the pre-install with the
    specified name.
    """
    sectionOpen = "%pre-install"

    def __init__(self, handler, **kwargs):
        super().__init__(handler, **kwargs)
        self.data = None
        self.interp = None
        self.error_on_fail = None
        self.log = None

    def handleHeader(self, lineno, args):
        """Handle a header of the current %pre-install section.

        This method is called when the opening tag for a section is
        seen. Not all sections will need this method, though all
        provided with kickstart include one.

        :param lineno: a number of the current line
        :param args: a list of strings passed as arguments
        """
        super().handleHeader(lineno, args)

        if not args:
            raise KickstartParseError(
                _("Missing name of the %pre-install section."),
                lineno=lineno
            )

        name = args[1]
        arguments = args[2:]
        data = getattr(self.handler.pre_install, name, None)

        if not data:
            raise KickstartParseError(
                _("Unknown name of the %pre-install section."),
                lineno=lineno
            )

        self.data = data
        self.line_number = lineno
        self.data.handle_header(arguments, self.line_number)

    def handleLine(self, line):
        """Handle one line of the current %pre-install section.

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
        """Handle the end of the current %pre-install section.

        This method is called when the %end tag for a section is
        seen.
        """
        super().finalize()
        self.data.handle_end()
        self.data = None
