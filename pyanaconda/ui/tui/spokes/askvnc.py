# Ask vnc text spoke
#
# Copyright (C) 2012  Red Hat, Inc.
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
# Red Hat Author(s): Jesse Keating <jkeating@redhat.com>
#

from pyanaconda.ui.tui.spokes import NormalTUISpoke
from pyanaconda.ui.tui.simpleline import TextWidget, ColumnWidget
from pyanaconda.constants import USEVNC, USETEXT
from pyanaconda.constants_text import INPUT_PROCESSED
from pyanaconda.i18n import _
from pyanaconda.ui.communication import hubQ
from pyanaconda.ui.tui import exception_msg_handler
import getpass
import sys

def exception_msg_handler_and_exit(event, data):
    """Display an exception and exit so that we don't end up in a loop."""
    exception_msg_handler(event, data)
    sys.exit(1)

class AskVNCSpoke(NormalTUISpoke):
    title = _("VNC")
    category = "vnc"

    # This spoke is kinda standalone, not meant to be used with a hub
    # We pass in some fake data just to make our parents happy
    def __init__(self, app, data, storage=None, payload=None,
                 instclass=None, message=None):
        NormalTUISpoke.__init__(self, app, data, storage, payload, instclass)

        # The TUI hasn't been initialized with the message handlers yet. Add an
        # exception message handler so that the TUI exits if anything goes wrong
        # at this stage.
        self._app.register_event_handler(hubQ.HUB_CODE_EXCEPTION, exception_msg_handler_and_exit)

        if message:
            self._message = message
        else:
            self._message = _("X was unable to start on your "
                              "machine.  Would you like to "
                              "start VNC to connect to "
                              "this computer from another "
                              "computer and perform a "
                              "graphical installation or continue "
                              "with a text mode installation?")

        self._choices = (_(USEVNC), _(USETEXT))
        self._usevnc = False

    @property
    def indirect(self):
        return True

    def refresh(self, args = None):
        NormalTUISpoke.refresh(self, args)

        self._window += [TextWidget(self._message), ""]

        for idx, choice in enumerate(self._choices):
            number = TextWidget("%2d)" % (idx + 1))
            c = ColumnWidget([(3, [number]), (None, [TextWidget(choice)])], 1)
            self._window += [c, ""]

        return True

    def input(self, args, key):
        """Override input so that we can launch the VNC password spoke"""

        try:
            keyid = int(key) - 1
        except ValueError:
            return key

        if 0 <= keyid < len(self._choices):
            choice = self._choices[keyid]
        else:
            return INPUT_PROCESSED

        if choice == _(USETEXT):
            self._usevnc = False
        else:
            self._usevnc = True
            newspoke = VNCPassSpoke(self.app, self.data, self.storage,
                                    self.payload, self.instclass)
            self.app.switch_screen_modal(newspoke)

        self.apply()
        self.close()
        return INPUT_PROCESSED

    def apply(self):
        self.data.vnc.enabled = self._usevnc

class VNCPassSpoke(NormalTUISpoke):
    title = _("VNC Password")
    category = "vnc"

    def __init__(self, app, data, storage, payload, instclass, message=None):
        NormalTUISpoke.__init__(self, app, data, storage, payload, instclass)
        self._password = ""
        if message:
            self._message = message
        else:
            self._message = _("Please provide VNC password. You will have to type it twice. \n"
                              "Leave blank for no password")

    @property
    def indirect(self):
        return True

    @property
    def completed(self):
        return True # We're always complete

    def refresh(self, args = None):
        NormalTUISpoke.refresh(self, args)
        self._window += [TextWidget(self._message), ""]

        return True

    def prompt(self, args = None):
        """Override prompt as password typing is special."""
        p1 = getpass.getpass(_("Password: "))
        p2 = getpass.getpass(_("Password (confirm): "))

        if p1 != p2:
            print _("Passwords do not match!")
            return None
        elif 0 < len(p1) < 6:
            print _("The password must be at least "
                    "six characters long.")
            return None
        else:
            self._password = p1
            self.apply()

        self.close()

    def apply(self):
        self.data.vnc.password = self._password
