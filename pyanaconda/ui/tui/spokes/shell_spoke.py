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
# Red Hat Author(s): Vratislav Podzimek <vpodzime@redhat.com>
#

"""Text mode shell spoke"""

from pyanaconda.ui.tui.spokes import NormalTUISpoke
from pyanaconda.ui.tui.simpleline.widgets import TextWidget
from pyanaconda.i18n import _
from pyanaconda.constants import ANACONDA_ENVIRON
from blivet import arch

import subprocess

class ShellSpoke(NormalTUISpoke):
    title = _("Shell")
    category = "system"

    @classmethod
    def should_run(cls, environment, data):
        # run only in the installer on s390(x) machines
        return environment == ANACONDA_ENVIRON and arch.isS390()

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

        self._window += [TextWidget(_("Exit the shell to continue")), ""]

    def prompt(self, args=None):
        # run shell instead of printing prompt and close window on shell exit
        proc = subprocess.Popen(["bash", "--login"], shell=True, cwd="/")
        proc.wait()
        self.close()

        # suppress the prompt
        return None
