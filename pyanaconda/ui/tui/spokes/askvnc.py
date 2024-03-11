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
import sys

from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.ui.tui.spokes import NormalTUISpoke
from pyanaconda.core.constants import USEVNC, USETEXT, QUIT_MESSAGE
from pyanaconda.core.i18n import N_, _
from pyanaconda.ui.tui import exception_msg_handler
from pyanaconda.core.util import execWithRedirect, ipmi_abort

from simpleline import App
from simpleline.event_loop.signals import ExceptionSignal
from simpleline.render.containers import ListColumnContainer
from simpleline.render.prompt import Prompt
from simpleline.render.screen import InputState
from simpleline.render.screen_handler import ScreenHandler
from simpleline.render.adv_widgets import YesNoDialog
from simpleline.render.widgets import TextWidget


def exception_msg_handler_and_exit(signal, data):
    """Display an exception and exit so that we don't end up in a loop."""
    exception_msg_handler(signal, data)
    sys.exit(1)


class AskVNCSpoke(NormalTUISpoke):
    """
       .. inheritance-diagram:: AskVNCSpoke
          :parts: 3
    """
    title = N_("VNC")

    # This spoke is kinda standalone, not meant to be used with a hub
    # We pass in some fake data just to make our parents happy
    def __init__(self, data, storage=None, payload=None, message=""):
        super().__init__(data, storage, payload)
        self.input_required = True
        self.initialize_start()
        self._container = None

        # The TUI hasn't been initialized with the message handlers yet. Add an
        # exception message handler so that the TUI exits if anything goes wrong
        # at this stage.
        loop = App.get_event_loop()
        loop.register_signal_handler(ExceptionSignal, exception_msg_handler_and_exit)
        self._message = message
        self._use_rd = False
        self.initialize_done()

    @property
    def indirect(self):
        return True

    def refresh(self, args=None):
        super().refresh(args)

        self.window.add_with_separator(TextWidget(self._message))

        self._container = ListColumnContainer(1, spacing=1)

        # choices are
        # USE VNC
        self._container.add(TextWidget(_(USEVNC)), self._use_vnc_callback)
        # USE TEXT
        self._container.add(TextWidget(_(USETEXT)), self._use_text_callback)

        self.window.add_with_separator(self._container)

    def _use_vnc_callback(self, data):
        self._use_rd = True
        new_spoke = VNCPassSpoke(self.data, self.storage, self.payload)
        ScreenHandler.push_screen_modal(new_spoke)

    def _use_text_callback(self, data):
        self._use_rd = False

    def input(self, args, key):
        """Override input so that we can launch the VNC password spoke"""
        if self._container.process_user_input(key):
            self.apply()
            return InputState.PROCESSED_AND_CLOSE
        else:
            if key.lower() == Prompt.QUIT:
                d = YesNoDialog(_(QUIT_MESSAGE))
                ScreenHandler.push_screen_modal(d)
                if d.answer:
                    ipmi_abort(scripts=self.data.scripts)
                    if conf.system.can_reboot:
                        execWithRedirect("systemctl", ["--no-wall", "reboot"])
                    else:
                        sys.exit(1)
            else:
                return super().input(args, key)

    def apply(self):
        self.data.vnc.enabled = self._use_rd


class VNCPassSpoke(NormalTUISpoke):
    """
       .. inheritance-diagram:: VNCPassSpoke
          :parts: 3
    """

    def __init__(self, data, storage, payload, message=None):
        super().__init__(data, storage, payload)
        self.title = N_("VNC Password")
        self._password = ""
        if message:
            self._message = message
        else:
            self._message = _("Please provide VNC password (must be six to eight characters long).\n"
                              "You will have to type it twice. Leave blank for no password")

    @property
    def indirect(self):
        return True

    @property
    def completed(self):
        return True # We're always complete

    def refresh(self, args=None):
        super().refresh(args)
        self.window.add_with_separator(TextWidget(self._message))

    def prompt(self, args=None):
        """Override prompt as password typing is special."""
        p1 = self.get_user_input(_("Password: "), True)
        p2 = self.get_user_input(_("Password (confirm): "), True)

        if p1 != p2:
            self._print_error_and_redraw(_("Passwords do not match!"))
        elif 0 < len(p1) < 6:
            self._print_error_and_redraw((_("The password must be at least "
                                            "six characters long.")))
        elif len(p1) > 8:
            self._print_error_and_redraw(_("The password cannot be more than "
                                           "eight characters long."))
        else:
            self._password = p1
            self.apply()
            self.close()

        # ruff: noqa: PLR1711
        return None

    def _print_error_and_redraw(self, msg):
        print(msg)
        self.redraw()

    def apply(self):
        self.data.vnc.password = self._password
