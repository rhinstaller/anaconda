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


class StorageISCSIHelpers():
    def __init__(
            self,
            server=None,
            client=None,
            target_iqn="iqn.2015-09.cockpit.lan",
            initiator_iqn="iqn.2015-10.cockpit.lan"
    ):
        self.server = server
        self.client = client
        self.target_iqn = target_iqn
        self.initiator_iqn = initiator_iqn
        self.user_name = "admin"
        self.discovery_password = "foobar"
        self.auth_password = "barfoo"

    def setup_iscsi_server(self):
        # Setup a iSCSI target with authentication for discovery
        self.server.execute("""
                  export TERM=dumb
                  targetcli /backstores/ramdisk create test 50M
                  targetcli /iscsi set discovery_auth enable=1 userid=admin password=%(discovery_password)s
                  targetcli /iscsi create %(tgt)s
                  targetcli /iscsi/%(tgt)s/tpg1/luns create /backstores/ramdisk/test
                  targetcli /iscsi/%(tgt)s/tpg1 set attribute authentication=1
                  targetcli /iscsi/%(tgt)s/tpg1/acls create %(ini)s
                  targetcli /iscsi/%(tgt)s/tpg1/acls/%(ini)s set auth userid=admin password=%(auth_password)s
                  """ % {
                      "tgt": self.target_iqn,
                      "ini": self.initiator_iqn,
                      "discovery_password": self.discovery_password,
                      "auth_password": self.auth_password
                    })
        self.server.execute("""
                  firewall-cmd --add-port=3260/tcp --permanent
                  systemctl reload firewalld""")

    def get_initiator_iqn(self):
        return self.client.execute("sed </etc/iscsi/initiatorname.iscsi -e 's/^.*=//'").rstrip()


class StorageISCSIDiscoverDialog():
    def __init__(self, browser, initiator_iqn=None, address=None, username=None, password=None):
        self.address = address
        self.browser = browser
        self.initiator_iqn = initiator_iqn
        self.password = password
        self.username = username

    def open(self):
        self.browser.click("#configure-specialized-disks-button")
        self.browser.click("#add-iscsi-target-dialog-button")
        self.browser.wait_visible("#add-iscsi-target-dialog-discover-modal")

    def cancel(self):
        self.browser.click("#add-iscsi-target-dialog-cancel")
        self.browser.wait_not_present("#add-iscsi-target-dialog-discover-modal")

    def fill(self):
        self.browser.set_input_text("#add-iscsi-target-dialog-initiator-name", self.initiator_iqn)
        self.browser.set_input_text("#add-iscsi-target-dialog-target-ip-address", self.address)
        self.browser.set_input_text("#add-iscsi-target-dialog-discovery-username", self.username)
        self.browser.set_input_text("#add-iscsi-target-dialog-discovery-password", self.password)

    def submit(self, xfail=None):
        self.browser.click("#add-iscsi-target-dialog-discover")
        if xfail:
            self.browser.wait_in_text("#add-iscsi-target-dialog-error", xfail)

    def check_available_targets(self, targets):
        for idx, target in enumerate(targets):
            self.browser.wait_in_text(
                f"#add-iscsi-target-dialog-available-targets li:nth-child({idx + 1})",
                target
            )

    def login(self, target):
        self.browser.click(
            f"#add-iscsi-target-dialog-available-targets li:contains({target}) button:contains(Login)"
        )


class StorageISCSILoginDialog():
    def __init__(self, browser, target, username, password):
        self.browser = browser
        self.password = password
        self.target = target
        self.username = username

    def cancel(self):
        self.browser.click("#add-iscsi-target-dialog-cancel")
        self.browser.wait_not_present("#add-iscsi-target-dialog-discover-modal")

    def fill(self):
        self.browser.set_input_text("#add-iscsi-target-dialog-chap-username", self.username)
        self.browser.set_input_text("#add-iscsi-target-dialog-chap-password", self.password)

    def submit(self, xfail=None):
        self.browser.click("#add-iscsi-target-dialog-login")
        if not xfail:
            self.browser.wait_not_present("#add-iscsi-target-dialog-login-modal")
        else:
            self.browser.wait_in_text("#add-iscsi-target-dialog-error", xfail)
