#
# network_gui.py: Network configuration dialog
#
# Copyright (C) 2000, 2001, 2002, 2003, 2004, 2005, 2006,  Red Hat, Inc.
#               2007, 2008, 2009
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
# Author(s): Michael Fulbright <msf@redhat.com>
#            David Cantrell <dcantrell@redhat.com>
#

import string
from iw_gui import *
import gui
import network

from constants import *
import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class NetworkWindow(InstallWindow):
    def getScreen(self, anaconda):
        self.intf = anaconda.intf
        self.anaconda = anaconda
        self.hostname = network.getDefaultHostname(anaconda)

        # load the UI
        (self.xml, self.align) = gui.getGladeWidget("network.glade",
                                                    "network_align")
        self.icon = self.xml.get_widget("icon")
        self.hostnameEntry = self.xml.get_widget("hostnameEntry")
        self.hostnameEntry.set_text(self.hostname)

        # pressing Enter in confirm == clicking Next
        self.hostnameEntry.connect("activate",
                                   lambda w: self.ics.setGrabNext(1))

        # load the icon
        gui.readImageFromFile("network.png", image=self.icon)

        return self.align

    def focus(self):
        self.hostnameEntry.grab_focus()

    def hostnameError(self):
        self.hostnameEntry.grab_focus()
        raise gui.StayOnScreen

    def getNext(self):
        hostname = string.strip(self.hostnameEntry.get_text())
        herrors = network.sanityCheckHostname(hostname)

        if not hostname:
            self.intf.messageWindow(_("Error with Hostname"),
                                    _("You must enter a valid hostname for this "
                                      "computer."), custom_icon="error")
            self.hostnameError()

        if herrors is not None:
            self.intf.messageWindow(_("Error with Hostname"),
                                    _("The hostname \"%(hostname)s\" is not "
                                      "valid for the following reason:\n\n"
                                      "%(herrors)s")
                                    % {'hostname': hostname,
                                       'herrors': herrors},
                                    custom_icon="error")
            self.hostnameError()

        self.anaconda.network.hostname = hostname
        return None
