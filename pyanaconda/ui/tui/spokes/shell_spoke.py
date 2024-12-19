#
# Copyright (C) 2013  Red Hat, Inc.
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
"""Text mode shell spoke"""

from blivet import arch
from simpleline.render.widgets import TextWidget

from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import ANACONDA_ENVIRON
from pyanaconda.core.i18n import N_, _
from pyanaconda.core.util import execConsole
from pyanaconda.ui.categories.system import SystemCategory
from pyanaconda.ui.tui.spokes import NormalTUISpoke

__all__ = ["ShellSpoke"]


class ShellSpoke(NormalTUISpoke):
    """
       .. inheritance-diagram:: ShellSpoke
          :parts: 3
    """
    category = SystemCategory

    @staticmethod
    def get_screen_id():
        """Return a unique id of this UI screen."""
        return "shell"

    def __init__(self, data, storage, payload):
        super().__init__(data, storage, payload)
        self.title = N_("Shell")

    @classmethod
    def should_run(cls, environment, data):
        # run only in the installer on s390(x) machines
        return conf.anaconda.debug or (environment == ANACONDA_ENVIRON and arch.is_s390())

    @property
    def completed(self):
        # always completed
        return True

    @property
    def status(self):
        return _("Start shell")

    def apply(self):
        # no action needed here
        pass

    def refresh(self, args=None):
        NormalTUISpoke.refresh(self, args)
        self.window.add_with_separator(TextWidget(_("Exit the shell to continue")))

    # pylint: disable-next=useless-return
    def prompt(self, args=None):
        # run shell instead of printing prompt and close window on shell exit
        execConsole()
        self.close()

        # suppress the prompt
        # ruff: noqa: PLR1711
        return None
