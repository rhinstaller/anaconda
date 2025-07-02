# The main file for anaconda Cockpit interface
#
# Copyright (C) (2021)  Red Hat, Inc.
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
import os
from contextlib import contextmanager

import meh

from pyanaconda import ui
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import (
    PAYLOAD_TYPE_DNF,
    QUIT_MESSAGE,
    WEBUI_VIEWER_PID_FILE,
)
from pyanaconda.core.path import touch
from pyanaconda.core.util import startProgram
from pyanaconda.flags import flags

log = get_module_logger(__name__)

FIREFOX_THEME_DEFAULT = "default"
FIREFOX_THEME_LIVE = "live"

class CockpitUserInterface(ui.UserInterface):
    """This is the main class for Cockpit user interface."""

    def __init__(self, storage, payload, remote,
                 productTitle="Anaconda",
                 quitMessage=QUIT_MESSAGE):
        """
        For detailed description of the arguments see
        the parent class.

        :param storage: storage backend reference
        :type storage: instance of pyanaconda.Storage

        :param payload: payload (usually dnf) reference
        :type payload: instance of payload handler

        :param remote: if used run a cockpit-ws process to allow
                       passwordless remote access to the anaconda-webui for easier testing.
        :type remote: bool

        :param productTitle: the name of the product
        :type productTitle: str

        :param quitMessage: The text to be used in quit
                            dialog question. It should not
                            be translated to allow for change
                            of language.
        :type quitMessage: str
        """

        super().__init__(storage, payload)
        self.productTitle = productTitle
        self.remote = remote
        self.quitMessage = quitMessage
        self._meh_interface = meh.ui.text.TextIntf()
        self._main_loop = None
        self._viewer_pid_file = WEBUI_VIEWER_PID_FILE

    def setup(self, data):
        """Construct all the objects required to implement this interface.

        This method must be provided by all subclasses.
        """
        # FIXME: Support automated installations in Web UI.
        if flags.automatedInstall and flags.ksprompt:
            raise NotImplementedError("Automated installations are not supported by Web UI.")

        # FIXME: Support non-interactive installations in Web UI.
        if flags.automatedInstall and not flags.ksprompt:
            raise NotImplementedError("Non-interactive installations are not supported by Web UI.")

        # Make sure that Web UI can be used only for hardware installations.
        if conf.target.is_directory or conf.target.is_image:
            raise RuntimeError("Dir and image installations are not supported by Web UI.")

        # Make sure that Web UI can be used only on boot.iso or Live media.
        if not conf.system.supports_web_ui:
            raise RuntimeError("This installation environment is not supported by Web UI.")

        # FIXME: Support package installations in Web UI.
        if self.payload.type == PAYLOAD_TYPE_DNF:
            raise NotImplementedError("Package installations are not supported by Web UI.")

    def _print_message(self, msg):
        """Print a message to stdout."""
        print(msg)
        log.debug(msg)

    def run(self):
        """Run the interface."""
        log.debug("web-ui: starting cockpit web view")

        self._run_webui()

    def _run_webui(self):
        # FIXME: This part should be start event loop (could use the WatchProcesses class)
        # FIXME: We probably want to move this to early execution similar to what we have on live
        profile_name = FIREFOX_THEME_DEFAULT

        try:
            proc = startProgram(
                ["/usr/libexec/anaconda/webui-desktop",
                 "-t", profile_name, "-r", str(int(self.remote)),
                 "/cockpit/@localhost/anaconda-webui/index.html"],
                reset_lang=False
            )

            log.debug("cockpit web view has been started")
            with open(self._viewer_pid_file, "w") as f:
                f.write(repr(proc.pid))

            (output_string, err_string) = proc.communicate()

            if type(output_string) is bytes:
                output_string = output_string.decode("utf-8")

            if output_string and output_string[-1] != "\n":
                output_string = output_string + "\n"

            if output_string:
                for line in output_string.splitlines():
                    log.info(line)

            if err_string:
                log.error("Errors from webui-desktop:")
                for line in err_string.splitlines():
                    log.error(line)

        except OSError as e:
            log.error(".... %s", e)
            raise

    @property
    def meh_interface(self):
        return self._meh_interface

    @property
    def tty_num(self):
        return 6

    def showError(self, message):
        """Print the error."""
        self._print_message(message)

    def showDetailedError(self, message, details, buttons=None):
        """Print the detailed error."""
        self._print_message(message + "\n\n" + details)
        return False

    def showYesNoQuestion(self, message):
        """Answer no by default."""
        log.debug("Skipping the following question: %s", message)
        return False
