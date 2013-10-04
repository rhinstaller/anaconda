# User creation text spoke
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
# Red Hat Author(s): Martin Sivak <msivak@redhat.com>
#

from pyanaconda.ui.tui.spokes import EditTUISpoke
from pyanaconda.ui.tui.spokes import EditTUISpokeEntry as Entry
from pyanaconda.ui.common import FirstbootSpokeMixIn
from pyanaconda.users import guess_username
from pyanaconda.i18n import _
from pykickstart.constants import FIRSTBOOT_RECONFIG
from pyanaconda.constants import ANACONDA_ENVIRON, FIRSTBOOT_ENVIRON
from pyanaconda.regexes import GECOS_VALID, USERNAME_VALID, GROUPLIST_SIMPLE_VALID

__all__ = ["UserSpoke"]

class UserSpoke(FirstbootSpokeMixIn, EditTUISpoke):
    title = _("Create user")
    category = "password"

    edit_fields = [
        Entry("Create user", "_create", EditTUISpoke.CHECK, True),
        Entry("Fullname", "gecos", GECOS_VALID, lambda self,args: args._create),
        Entry("Username", "name", USERNAME_VALID, lambda self,args: args._create),
        Entry("Use password", "_use_password", EditTUISpoke.CHECK, lambda self,args: args._create),
        Entry("Password", "_password", EditTUISpoke.PASSWORD, lambda self,args: args._use_password and args._create),
        Entry("Administrator", "_admin", EditTUISpoke.CHECK, lambda self,args: args._create),
        Entry("Groups", "_groups", GROUPLIST_SIMPLE_VALID, lambda self,args: args._create)
        ]

    @classmethod
    def should_run(cls, environment, data):
        # the user spoke should run always in the anaconda and in firstboot only
        # when doing reconfig or if no user has been created in the installation
        if environment == ANACONDA_ENVIRON:
            return True
        elif environment == FIRSTBOOT_ENVIRON and data is None:
            # cannot decide, stay in the game and let another call with data
            # available (will come) decide
            return True
        elif environment == FIRSTBOOT_ENVIRON and data and \
                (data.firstboot.firstboot == FIRSTBOOT_RECONFIG or \
                     len(data.user.userList) == 0):
            return True
        else:
            return False

    def __init__(self, app, data, storage, payload, instclass):
        FirstbootSpokeMixIn.__init__(self)
        EditTUISpoke.__init__(self, app, data, storage, payload, instclass)

        if self.data.user.userList:
            self.args = self.data.user.userList[0]
            self.args._create = True
        else:
            self.args = self.data.UserData()
            self.args._create = False

        self.args._use_password = self.args.isCrypted or self.args.password

        # Keep the password separate from the kickstart data until apply()
        # so that all of the properties are set at once
        self.args._password = ""

    def refresh(self, args = None):
        self.args._admin = "wheel" in self.args.groups
        self.args._groups = ", ".join(self.args.groups)
        return EditTUISpoke.refresh(self, args)

    @property
    def completed(self):
        """ Verify a user is created; verify pw is set if option checked. """
        if len(self.data.user.userList) > 0:
            if self.args._use_password and not bool(self.args.password or self.args.isCrypted):
                return False
            else:
                return True
        else:
            return False

    @property
    def mandatory(self):
        """ Only mandatory if root account is disabled. """
        return not bool(self.data.rootpw.password) or self.data.rootpw.lock

    @property
    def status(self):
        if len(self.data.user.userList) == 0:
            return _("No user will be created")
        elif self.args._use_password and not bool(self.args.password or self.args.isCrypted):
            return _("You must set a password")
        elif "wheel" in self.data.user.userList[0].groups:
            return _("Administrator %s will be created") % self.data.user.userList[0].name
        else:
            return _("User %s will be created") % self.data.user.userList[0].name

    def apply(self):
        if self.args.gecos and not self.args.name:
            username = guess_username(self.args.gecos)
            if USERNAME_VALID.match(username):
                self.args.name = guess_username(self.args.gecos)

        self.args.groups = [g.strip() for g in self.args._groups.split(",") if g]

        # Add or remove the user from wheel group
        if self.args._admin and "wheel" not in self.args.groups:
            self.args.groups.append("wheel")
        elif not self.args._admin and "wheel" in self.args.groups:
            self.args.groups.remove("wheel")

        # Add or remove the user from userlist as needed
        if self.args._create and (self.args not in self.data.user.userList):
            self.data.user.userList.append(self.args)
        elif (not self.args._create) and (self.args in self.data.user.userList):
            self.data.user.userList.remove(self.args)

        # encrypt and store password only if user entered anything; this should
        # preserve passwords set via kickstart
        if self.args._use_password and len(self.args._password) > 0:
            self.args.password = self.args._password
            self.args.isCrypted = True
            self.args.password_kickstarted = False
        # clear pw when user unselects to use pw
        else:
            self.args.password = ""
            self.args.isCrypted = False
            self.args.password_kickstarted = False
