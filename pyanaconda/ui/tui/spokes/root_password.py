# Root password text spoke
#
# Copyright (C) 2012-2014  Red Hat, Inc.
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

from pyanaconda.ui.categories.user_settings import UserSettingsCategory
from pyanaconda.ui.tui.tuiobject import PasswordDialog
from pyanaconda.ui.tui.spokes import NormalTUISpoke
from pyanaconda.ui.common import FirstbootSpokeMixIn
from pyanaconda.flags import flags
from pyanaconda.i18n import N_, _

from simpleline.render.widgets import TextWidget


class PasswordSpoke(FirstbootSpokeMixIn, NormalTUISpoke):
    """
       .. inheritance-diagram:: PasswordSpoke
          :parts: 3
    """
    helpFile = "PasswordSpoke.txt"
    category = UserSettingsCategory

    def __init__(self, data, storage, payload, instclass):
        NormalTUISpoke.__init__(self, data, storage, payload, instclass)
        self.initialize_start()
        self.title = N_("Root password")
        self.input_required = False

        self._policy = self.data.anaconda.pwpolicy.get_policy("root", fallback_to_default=True)
        self._password = None
        self.initialize_done()

    @property
    def completed(self):
        return bool(self.data.rootpw.password or self.data.rootpw.lock)

    @property
    def showable(self):
        return not (self.completed and flags.automatedInstall and not self._policy.changesok)

    @property
    def mandatory(self):
        return not any(user for user in self.data.user.userList
                       if "wheel" in user.groups)

    @property
    def status(self):
        if self.data.rootpw.password:
            return _("Password is set.")
        elif self.data.rootpw.lock:
            return _("Root account is disabled.")
        else:
            return _("Password is not set.")

    def refresh(self, args=None):
        NormalTUISpoke.refresh(self, args)

        msg = _("Please select new root password. You will have to type it twice.")
        self.window.add_with_separator(TextWidget(msg))

    def show_all(self):
        super().show_all()

        password_dialog = PasswordDialog(_("Password"), policy=self._policy)
        password_dialog.no_separator = True

        self._password = password_dialog.run()

        if self._password is None:
            self.redraw()
            return
        else:
            self.apply()
            self.close()

    def apply(self):
        self.data.rootpw.password = self._password
        self.data.rootpw.isCrypted = True
        self.data.rootpw.lock = False
        self.data.rootpw.seen = False
