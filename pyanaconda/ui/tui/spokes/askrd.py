# Ask Remote Desktop text spoke
#
# Asks the user if a text mode or remote desktop based access should be used.
#
# Copyright (C) 2024  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import sys

from simpleline import App
from simpleline.event_loop.signals import ExceptionSignal
from simpleline.render.adv_widgets import YesNoDialog
from simpleline.render.containers import ListColumnContainer
from simpleline.render.prompt import Prompt
from simpleline.render.screen import InputState
from simpleline.render.screen_handler import ScreenHandler
from simpleline.render.widgets import TextWidget

from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import QUIT_MESSAGE, USERDP, USETEXT
from pyanaconda.core.i18n import N_, _
from pyanaconda.core.util import execWithRedirect, ipmi_abort
from pyanaconda.ui.tui import exception_msg_handler
from pyanaconda.ui.tui.spokes import NormalTUISpoke


def exception_msg_handler_and_exit(signal, data):
    """Display an exception and exit so that we don't end up in a loop."""
    exception_msg_handler(signal, data)
    sys.exit(1)


class AskRDSpoke(NormalTUISpoke):
    """
       .. inheritance-diagram:: AskRDPSpoke
          :parts: 3
    """
    title = N_("RDP")

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
        self._rdp_username = ""
        self._rdp_password = ""
        self._use_rd = False
        self.initialize_done()

    @property
    def use_remote_desktop(self):
        """Should a remote desktop solution be used instead of text mode ?"""
        return self._use_rd

    @property
    def rdp_username(self):
        """User provided RDP user name (if any)."""
        return self._rdp_username

    @property
    def rdp_password(self):
        """User provided RDP password (if any)."""
        return self._rdp_password

    @property
    def indirect(self):
        return True

    def refresh(self, args=None):
        super().refresh(args)

        self.window.add_with_separator(TextWidget(self._message))

        self._container = ListColumnContainer(1, spacing=1)

        # choices are
        # USE RDP
        self._container.add(TextWidget(_(USERDP)), self._use_rdp_callback)
        # USE TEXT
        self._container.add(TextWidget(_(USETEXT)), self._use_text_callback)

        self.window.add_with_separator(self._container)

    def _use_rdp_callback(self, data):
        self._use_rd = True
        new_rdp_spoke = RDPAuthSpoke(self.data)
        ScreenHandler.push_screen_modal(new_rdp_spoke)
        self._rdp_username = new_rdp_spoke._username
        self._rdp_password = new_rdp_spoke._password

    def _use_text_callback(self, data):
        self._use_rd = False

    def input(self, args, key):
        """Override input so that we can launch the RDP user name & password spoke"""
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
        pass


class RDPAuthSpoke(NormalTUISpoke):
    """
       .. inheritance-diagram:: RDPAuthSpoke
          :parts: 3
    """

    def __init__(self, data, username=None, password=None):
        super().__init__(data, storage=None, payload=None)
        self.title = N_("RDP User name & Password")

        if username is not None:
            self._username = username
        else:
            self._username = ""

        if password is not None:
            self._password = password
        else:
            self._password = ""

    @property
    def indirect(self):
        return True

    @property
    def completed(self):
        return True  # We're always complete

    def refresh(self, args=None):
        super().refresh(args)
        self.window.add_with_separator(TextWidget(self.message))

    @property
    def message(self):
        text = ""
        if not self._username and not self._password:
            text = _("Please provide RDP user name & password.")
        elif self._username:
            text = _("Please provide RDP password.")
        else:
            text = _("Please provide RDP user name.")

        # if we want the password, add a note about typing it twice
        if not self._password:
            text = text + "\n" + _("You will have to type the password twice.")

        return text

    def prompt(self, args=None):
        """Override prompt as password typing is special."""
        # first make sure username is set
        if not self._username:
            username = self.get_user_input(_("User name: "), False)
            if username:
                self._username = username
            else:
                self._print_error_and_redraw(_("User name not set!"))
                return None

        # next try to get the password
        if not self._password:
            p1 = self.get_user_input(_("Password: "), True)
            p2 = self.get_user_input(_("Password (confirm): "), True)

            if p1 != p2:
                self._print_error_and_redraw(_("Passwords do not match!"))
                return None
            elif not p1:
                self._print_error_and_redraw((_("The password must not be empty.")))
                return None
            elif 0 < len(p1) < 6:
                self._print_error_and_redraw((_("The password must be at least "
                                                "six characters long.")))
                return None
            else:
                self._password = p1

        # do we finally have everything ?
        if self._username and self._password:
            self.apply()
            self.close()

        # ruff: noqa: PLR1711
        return None

    def _print_error_and_redraw(self, msg):
        print(msg)
        self.redraw()

    def apply(self):
        pass
