# Upgrade spoke classes
#
# Copyright (C) 2011  Red Hat, Inc.
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
# Red Hat Author(s): Chris Lumens <clumens@redhat.com>
#

from gi.repository import Gtk, AnacondaWidgets
from pyanaconda.ui.gui.hubs.summary import SummaryHub
from pyanaconda.ui.gui.spokes import StandaloneSpoke

__all__ = ["UpgradeSpoke"]

class UpgradeSpoke(StandaloneSpoke):
    mainWidgetName = "upgradeWindow"
    uiFile = "spokes/upgrade.ui"

    preForHub = SummaryHub
    priority = 10

    def apply(self):
        checkbox = self.builder.get_object("upgradeCheckbox")
        self.data.upgrade.upgrade = checkbox.get_active()

    def populate(self):
        from pyanaconda.product import productName, productVersion

        StandaloneSpoke.populate(self)

        # Set the label indicating what distribution we found and what
        # distribution we're trying to install.
        label = self.builder.get_object("promiseLabel")
        label.set_text(label.get_text() % {"installedDistro": "Fedora 15",
                                           "newDistro": "%s %s" % (productName, productVersion)})

        # Add an icon for every user account we found.
        usersBox = self.builder.get_object("usersBox")
        userSelector = AnacondaWidgets.SpokeSelector(title="beefymiracle", status="/home/beefymiracle")
        usersBox.add(userSelector)

        # And then set up the details about where home directories were found.
        deviceSelector = self.builder.get_object("deviceSelector")
        deviceSelector.set_property("title", "160 GB Solid-State Disk")
        deviceSelector.set_property("status", "ATA INTEL BLAH BLAH BLAH")
        partitionSelector = self.builder.get_object("partitionSelector")
        partitionSelector.set_property("title", "Physical Partition")
        partitionSelector.set_property("status", "60 GB")
        mountPointSelector = self.builder.get_object("mountPointSelector")
        mountPointSelector.set_property("title", "/home")
