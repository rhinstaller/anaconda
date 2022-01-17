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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

from pyanaconda import ui
from pyanaconda.core.constants import QUIT_MESSAGE
from pyanaconda.core.util import startProgram

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class CockpitUserInterface(ui.UserInterface):
    """This is the main class for Cockpit user interface."""

    def __init__(self, storage, payload,
                 productTitle="Anaconda", isFinal=True,
                 quitMessage=QUIT_MESSAGE):
        """
        For detailed description of the arguments see
        the parent class.

        :param storage: storage backend reference
        :type storage: instance of pyanaconda.Storage

        :param payload: payload (usually dnf) reference
        :type payload: instance of payload handler

        :param productTitle: the name of the product
        :type productTitle: str

        :param isFinal: Boolean that marks the release
                        as final (True) or development
                        (False) version.
        :type isFinal: bool

        :param quitMessage: The text to be used in quit
                            dialog question. It should not
                            be translated to allow for change
                            of language.
        :type quitMessage: str
        """

        super().__init__(storage, payload)

        self.productTitle = productTitle
        self.isFinal = isFinal
        self.quitMessage = quitMessage

    def setup(self, data):
        """Construct all the objects required to implement this interface.

        This method must be provided by all subclasses.
        """
        pass

    def run(self):
        """Run the interface."""
        log.debug("web-ui: starting cockpit web view")
        proc = startProgram(["/usr/libexec/cockpit-desktop",
                            "/cockpit/@localhost/anaconda-webui/index.html"],
                            reset_lang=False)
        log.debug("cockpit web view has been started")
        proc.wait()
        log.debug("cockpit web view has finished running")
        return

    @property
    def meh_interface(self):
        # FIXME: actually implement this
        return True

    @property
    def tty_num(self):
        # FIXME: actually implement this
        return 6

    def showError(self, message):
        # FIXME: actually implement this
        return True

    def showDetailedError(self, message, details, buttons=None):
        # FIXME: actually implement this
        return True

    def showYesNoQuestion(self, message):
        # FIXME: actually implement this
        return True
