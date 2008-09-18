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
import socket
from snack import *
from constants_text import *
from constants import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

class HostnameWindow:
    def hostTypeCb(self, (radio, hostEntry)):
        if radio.getSelection() != "manual":
            sense = FLAGS_SET
        else:
            sense = FLAGS_RESET

        hostEntry.setFlags(FLAG_DISABLED, sense)

    def __call__(self, screen, anaconda):
        devices = anaconda.id.network.available ()
        if not devices:
            return INSTALL_NOOP

        self.hostname = anaconda.id.network.hostname

        if self.hostname is None or self.hostname == '':
            self.hostname = socket.gethostname()

        if self.hostname == '':
            self.hostname = 'localhost.localdomain'

        thegrid = Grid(2, 2)
        radio = RadioGroup()
        autoCb = radio.add(_("automatically via DHCP"), "dhcp", 0)
        thegrid.setField(autoCb, 0, 0, growx = 1, anchorLeft = 1)

        manualCb = radio.add(_("manually"), "manual", 1)
        thegrid.setField(manualCb, 0, 1, anchorLeft = 1)
        hostEntry = Entry(24)
        hostEntry.set(anaconda.id.network.hostname)
        thegrid.setField(hostEntry, 1, 1, padding = (1, 0, 0, 0),
                         anchorLeft = 1)

        # disable the dhcp if we don't have any dhcp
        if network.anyUsingDHCP():
            autoCb.w.checkboxSetFlags(FLAG_DISABLED, FLAGS_RESET)
        else:
            autoCb.w.checkboxSetFlags(FLAG_DISABLED, FLAGS_SET)

        self.hostTypeCb((radio, hostEntry))

        autoCb.setCallback(self.hostTypeCb, (radio, hostEntry))
        manualCb.setCallback(self.hostTypeCb, (radio, hostEntry))

        toplevel = GridFormHelp(screen, _("Hostname Configuration"),
                                "hostname", 1, 4)
        text = TextboxReflowed(55,
                               _("If your system is part of a larger network "
                                 "where hostnames are assigned by DHCP, "
                                 "select automatically via DHCP. Otherwise, "
                                 "select manually and enter a hostname for "
                                 "your system. If you do not, your system "
                                 "will be known as 'localhost.'"))
        toplevel.add(text, 0, 0, (0, 0, 0, 1))

        bb = ButtonBar(screen, (TEXT_OK_BUTTON, TEXT_BACK_BUTTON))
        toplevel.add(thegrid, 0, 1, padding = (0, 0, 0, 1))
        toplevel.add(bb, 0, 2, growx = 1)

        while 1:
            result = toplevel.run()
            rc = bb.buttonPressed(result)

            if rc == TEXT_BACK_CHECK:
                screen.popWindow()
                return INSTALL_BACK

            if radio.getSelection() != "manual":
                anaconda.id.network.overrideDHCPhostname = False
                anaconda.id.network.hostname = "localhost.localdomain"
            else:
                hname = string.strip(hostEntry.value())
                if len(hname) == 0:
                    ButtonChoiceWindow(screen, _("Invalid Hostname"),
                                       _("You have not specified a hostname."),
                                       buttons = [ _("OK") ])
                    continue
                neterrors = network.sanityCheckHostname(hname)
                if neterrors is not None:
                    ButtonChoiceWindow(screen, _("Invalid Hostname"),
                                       _("The hostname \"%s\" is not valid "
                                         "for the following reason:\n\n%s")
                                       %(hname, neterrors),
                                       buttons = [ _("OK") ])
                    continue

                anaconda.id.network.overrideDHCPhostname = True
                anaconda.id.network.hostname = hname
            break

        screen.popWindow()
        return INSTALL_OK

# vim:tw=78:ts=4:et:sw=4
