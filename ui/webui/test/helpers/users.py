#!/usr/bin/python3
#
# Copyright (C) 2022 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; If not, see <http://www.gnu.org/licenses/>.

import os
import sys

HELPERS_DIR = os.path.dirname(__file__)
sys.path.append(HELPERS_DIR)

from password import Password
from step_logger import log_step


USERS_SERVICE = "org.fedoraproject.Anaconda.Modules.Users"
USERS_INTERFACE = USERS_SERVICE
USERS_OBJECT_PATH = "/org/fedoraproject/Anaconda/Modules/Users"

CREATE_ACCOUNT_ID_PREFIX = "accounts-create-account"


class UsersDBus():
    def __init__(self, machine):
        self.machine = machine
        self._bus_address = self.machine.execute("cat /run/anaconda/bus.address")

    def dbus_get_users(self):
        ret = self.machine.execute(f'busctl --address="{self._bus_address}" \
            get-property  \
            {USERS_SERVICE} \
            {USERS_OBJECT_PATH} \
            {USERS_INTERFACE} Users')

        return ret

    def dbus_clear_users(self):
        self.machine.execute(f'busctl --address="{self._bus_address}" \
            set-property  \
            {USERS_SERVICE} \
            {USERS_OBJECT_PATH} \
            {USERS_INTERFACE} Users aa{{sv}} 0')


class Users(UsersDBus):
    def __init__(self, browser, machine):
        self.browser = browser

        UsersDBus.__init__(self, machine)

    @log_step(snapshot_before=True)
    def set_user_account(self, user_account, append=False, value_check=True):
        sel = "#accounts-create-account-user-account"
        self.browser.set_input_text(sel, user_account, append=append, value_check=value_check)

    @log_step(snapshot_before=True)
    def check_user_account(self, user_account):
        sel = "#accounts-create-account-user-account"
        self.browser.wait_val(sel, user_account)

    @log_step(snapshot_before=True)
    def set_full_name(self, full_name, append=False, value_check=True):
        sel = "#accounts-create-account-full-name"
        self.browser.set_input_text(sel, full_name, append=append, value_check=value_check)

    @log_step(snapshot_before=True)
    def check_full_name(self, full_name):
        sel = "#accounts-create-account-full-name"
        self.browser.wait_val(sel, full_name)


def create_user(browser, machine):
    p = Password(browser, CREATE_ACCOUNT_ID_PREFIX)
    u = Users(browser, machine)

    password = "password"
    p.set_password(password)
    p.set_password_confirm(password)
    u.set_user_account("tester")


def dbus_reset_users(machine):
    UsersDBus(machine).dbus_clear_users()
