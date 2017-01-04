# Class for the Anaconda TUI prompt.
#
# Copyright (C) 2016  Red Hat, Inc.
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
# Author(s):  Vendula Poncova <vponcova@redhat.com>
#

from pyanaconda.i18n import C_, N_

import logging
log = logging.getLogger("anaconda")


class Prompt(object):
    """Class to create a prompt message with options."""

    # Default message of the prompt
    DEFAULT_MESSAGE = N_("Please make a selection from the above")

    # String to use in a prompt when we want users to press the key ENTER.
    ENTER = N_("ENTER")

    # TRANSLATORS: 'q' to quit
    QUIT = C_('TUI|Spoke Navigation', 'q')
    QUIT_DESCRIPTION = N_("to quit")

    # TRANSLATORS:'c' to continue
    CONTINUE = C_('TUI|Spoke Navigation', 'c')
    CONTINUE_DESCRIPTION = N_("to continue")

    # TRANSLATORS:'r' to refresh
    REFRESH = C_('TUI|Spoke Navigation', 'r')
    REFRESH_DESCRIPTION = N_("to refresh")

    # TRANSLATORS:'h' to help
    HELP = C_('TUI|Spoke Navigation', 'h')
    HELP_DESCRIPTION = N_("to help")

    def __init__(self, message=DEFAULT_MESSAGE):
        """
        :param message: the message of the prompt
        :type message: str|None
        """
        self.message = message
        self.options = dict()

    def set_message(self, message):
        """Set the prompt message.

        :param message: the message of the prompt
        :type message: str|None
        """
        self.message = message

    def add_option(self, key, description):
        """Add an option to the prompt.
        Causes a warning if the option already exists.

        :param key: the key for choosing the option
        :type key: str

        :param description: the description of the option
        :type description: str
        """
        if key in self.options:
            log.warning("The option '%s' does already exist in '%s'.", key, self)

        self.options[key] = description

    def update_option(self, key, description):
        """Update an option in the prompt.
        Causes a warning if the option does not exist.

        :param key: the key for choosing the option
        :type key: str

        :param description: the description of the option
        :type description: str
        """
        if key not in self.options:
            log.warning("The option '%s' does not exist in '%s'.", key, self)

        self.options[key] = description

    def add_refresh_option(self, description=REFRESH_DESCRIPTION):
        """Add the option to refresh."""
        self.add_option(Prompt.REFRESH, description)

    def add_continue_option(self, description=CONTINUE_DESCRIPTION):
        """Add the option to continue."""
        self.add_option(Prompt.CONTINUE, description)

    def add_quit_option(self, description=QUIT_DESCRIPTION):
        """Add the option to quit."""
        self.add_option(Prompt.QUIT, description)

    def add_help_option(self, description=HELP_DESCRIPTION):
        """Add the option to help."""
        self.add_option(Prompt.HELP, description)

    def remove_option(self, key):
        """Remove an option with the given key.

        :param key: the key of the option
        :type key: str

        :return: the removed option
        :rtype: str|None
        """
        return self.options.pop(key, None)

    def __str__(self):
        """Return the string representation of the prompt."""
        if not self.message and not self.options:
            return ""

        parts = []

        if self.message:
            parts.append(self.message)

        if self.options:
            opt_list = ["'%s' %s" % (key, self.options[key]) for key in sorted(self.options.keys())]
            opt_str = "[%s]" % ", ".join(opt_list)
            parts.append(opt_str)

        return " ".join(parts) + ": "
