# Root password text spoke
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
# Red Hat Author(s): Martin Sivak <msivak@redhat.com>
#                    Jesse Keating <jkeating@redhat.com>
#

from pyanaconda.ui.tui.spokes import NormalTUISpoke
from pyanaconda.ui.tui.simpleline import TextWidget
from pyanaconda.ui.tui import YesNoDialog
from pyanaconda.users import validatePassword
from pwquality import PWQError
import getpass

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)


class PasswordSpoke(NormalTUISpoke):
    title = _("Set root password")
    category = "password"

    def __init__(self, app, data, storage, payload, instclass):
        NormalTUISpoke.__init__(self, app, data, storage, payload, instclass)
        self._password = None

    @property
    def completed(self):
        return bool(self.data.rootpw.password or self.data.rootpw.lock)

    @property
    def status(self):
        if self.data.rootpw.password:
            return _("Password is set.")
        elif self.data.rootpw.lock:
            return _("Root account is disabled.")
        else:
            return _("Password is not set.")

    def refresh(self, args = None):
        NormalTUISpoke.refresh(self, args)

        self._window += [TextWidget(_("Please select new root password. You will have to type it twice.")), ""]

        return True

    def prompt(self, args = None):
        """Overriden prompt as password typing is special."""
        pw = getpass.getpass(_("Password: "))
        confirm = getpass.getpass(_("Password (confirm): "))

        error = None
        # just returning an error is either blank or mismatched
        # passwords.  Raising is because of poor quality.
        try:
            error = validatePassword(pw, confirm)
            if error:
                print(error)
                return None
        except PWQError as (e, msg):
            error = _("You have provided a weak password: %s. " % msg)
            error += _("\nWould you like to use it anyway?")
            question_window = YesNoDialog(self._app, error)
            self._app.switch_screen_modal(question_window)
            if not question_window.answer:
                return None

        self._password = pw
        self.apply()

        self.close()

    def apply(self):
        self.data.rootpw.password = self._password
        self.data.rootpw.isCrypted = False
        self.data.rootpw.lock = False
