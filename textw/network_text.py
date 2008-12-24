#
# network_text.py: text mode network configuration dialogs
#
# Copyright (C) 2000, 2001, 2002, 2003, 2004, 2005, 2006  Red Hat, Inc.
# All rights reserved.
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
# Author(s): Jeremy Katz <katzj@redhat.com>
#            Michael Fulbright <msf@redhat.com>
#            David Cantrell <dcantrell@redhat.com>
#

import string
import network
from snack import *
from constants_text import *
from constants import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

class HostnameWindow:
    def __call__(self, screen, anaconda):
        toplevel = GridFormHelp(screen, _("Hostname"), "hostname", 1, 3)
        text = TextboxReflowed(55,
                               _("Please name this computer.  The hostname "
                                 "identifies the computer on a network."))
        toplevel.add(text, 0, 0, (0, 0, 0, 1))

        hostEntry = Entry(55)
        hostEntry.set(network.getDefaultHostname(anaconda))
        toplevel.add(hostEntry, 0, 1, padding = (0, 0, 0, 1))

        bb = ButtonBar(screen, (TEXT_OK_BUTTON, TEXT_BACK_BUTTON))
        toplevel.add(bb, 0, 2, growx = 1)

        while 1:
            result = toplevel.run()
            rc = bb.buttonPressed(result)

            if rc == TEXT_BACK_CHECK:
                screen.popWindow()
                return INSTALL_BACK

            hostname = string.strip(hostEntry.value())
            herrors = network.sanityCheckHostname(hostname)

            if not hostname:
                ButtonChoiceWindow(_("Error with Hostname"),
                                   _("You must enter a valid hostname for this "
                                     "computer."),
                                   buttons = [ _("OK") ])
                continue

            if herrors is not None:
                ButtonChoiceWindow(_("Error with Hostname"),
                                    _("The hostname \"%s\" is not valid for the "
                                      "following reason:\n\n%s")
                                    % (hostname, herrors,),
                                    buttons = [ _("OK") ])
                continue

            anaconda.id.network.hostname = hostname
            break

        screen.popWindow()
        return INSTALL_OK

# vim:tw=78:ts=4:et:sw=4
