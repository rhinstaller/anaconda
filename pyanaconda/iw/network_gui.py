#
# network_gui.py: Network configuration dialog
#
# Copyright (C) 2000, 2001, 2002, 2003, 2004, 2005, 2006,  Red Hat, Inc.
#               2007, 2008, 2009
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author(s): Michael Fulbright <msf@redhat.com>
#            David Cantrell <dcantrell@redhat.com>
#

import string
from iw_gui import *
from pyanaconda import gui
from pyanaconda import network
from pyanaconda import iutil
from pyanaconda.flags import flags
import gobject
import subprocess
import gtk
from pyanaconda import isys

from pyanaconda.constants import *
import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

class NetworkWindow(InstallWindow):
    def getScreen(self, anaconda):
        self.intf = anaconda.intf
        self.anaconda = anaconda
        self.hostname = network.getDefaultHostname(anaconda)

        # load the UI
        (self.xml, self.align) = gui.getGladeWidget("network.glade",
                                                    "network_align")
        self.icon = self.xml.get_widget("icon")
        self.hostnameEntry = self.xml.get_widget("hostnameEntry")
        self.hostnameEntry.set_text(self.hostname)

        self.netconfButton = self.xml.get_widget("netconfButton")
        self.netconfButton.connect("clicked", self._netconfButton_clicked)
        if (len(self.anaconda.network.netdevices) == 0
            or flags.imageInstall
            or flags.livecdInstall):
            self.netconfButton.set_sensitive(False)

        # pressing Enter in confirm == clicking Next
        self.hostnameEntry.connect("activate",
                                   lambda w: self.ics.setGrabNext(1))

        # load the icon
        gui.readImageFromFile("network.png", image=self.icon)

        return self.align

    def _netconfButton_clicked(self, *args):
        setupNetwork(self.intf)

    def focus(self):
        self.hostnameEntry.grab_focus()

    def hostnameError(self):
        self.hostnameEntry.grab_focus()
        raise gui.StayOnScreen

    def getNext(self):
        hostname = string.strip(self.hostnameEntry.get_text())
        herrors = network.sanityCheckHostname(hostname)

        if not hostname:
            self.intf.messageWindow(_("Error with Hostname"),
                                    _("You must enter a valid hostname for this "
                                      "computer."), custom_icon="error")
            self.hostnameError()

        if herrors is not None:
            self.intf.messageWindow(_("Error with Hostname"),
                                    _("The hostname \"%(hostname)s\" is not "
                                      "valid for the following reason:\n\n"
                                      "%(herrors)s")
                                    % {'hostname': hostname,
                                       'herrors': herrors},
                                    custom_icon="error")
            self.hostnameError()

        self.anaconda.network.setHostname(hostname)
        return None

def NMCEExited(pid, condition, anaconda):
    if anaconda:
        anaconda.intf.icw.window.set_sensitive(True)

def setupNetwork(intf):
    intf.enableNetwork(just_setup=True)

# TODORV: get rid of setting sensitive completely?
def runNMCE(anaconda=None, blocking=True):
    if not blocking and anaconda:
        anaconda.intf.icw.window.set_sensitive(False)
    cmd = ["/usr/bin/nm-connection-editor"]
    out = open("/dev/tty5", "w")
    try:
        proc = subprocess.Popen(cmd, stdout=out, stderr=out)
    except Exception as e:
        if not blocking and anaconda:
            anaconda.intf.icw.window.set_sensitive(True)
        import logging
        log = logging.getLogger("anaconda")
        log.error("Could not start nm-connection-editor: %s" % e)
        return None
    else:
        if blocking:
            proc.wait()
        else:
            gobject.child_watch_add(proc.pid, NMCEExited, data=anaconda, priority=gobject.PRIORITY_DEFAULT)


def selectInstallNetDeviceDialog(network, devices = None):

    devs = devices or network.netdevices.keys()
    if not devs:
        return None
    devs.sort()

    dialog = gtk.Dialog(_("Select network interface"))
    dialog.add_button('gtk-cancel', gtk.RESPONSE_CANCEL)
    dialog.add_button('gtk-ok', 1)
    dialog.set_position(gtk.WIN_POS_CENTER)
    gui.addFrame(dialog)

    dialog.vbox.pack_start(gui.WrappingLabel(
        _("This requires that you have an active "
          "network connection during the installation "
          "process.  Please configure a network interface.")))

    combo = gtk.ComboBox()
    cell = gtk.CellRendererText()
    combo.pack_start(cell, True)
    combo.set_attributes(cell, text = 0)
    cell.set_property("wrap-width", 525)
    combo.set_size_request(480, -1)
    store = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
    combo.set_model(store)

    ksdevice = network.getKSDevice()
    if ksdevice:
        ksdevice = ksdevice.iface
    preselected = None

    for dev in devices:
        i = store.append(None)
        if not preselected:
            preselected = i

        desc = network.netdevices[dev].description
        if desc:
            desc = "%s - %s" %(dev, desc)
        else:
            desc = "%s" %(dev,)

        hwaddr = network.netdevices[dev].get("HWADDR")

        if hwaddr:
            desc = "%s - %s" %(desc, hwaddr,)

        if ksdevice and ksdevice == dev:
            preselected = i

        store[i] = (desc, dev)

    combo.set_active_iter(preselected)
    dialog.vbox.pack_start(combo)

    dialog.show_all()

    rc = dialog.run()

    if rc in [gtk.RESPONSE_CANCEL, gtk.RESPONSE_DELETE_EVENT]:
        install_device = None
    else:
        active = combo.get_active_iter()
        install_device = combo.get_model().get_value(active, 1)

    dialog.destroy()
    return install_device

def selectSSIDsDialog(devssids):
    """Dialog for access point selection.

    devssids - dict iface->[ssid1, ssid2, ssid3, ...]
    returns  - dict iface->[ssidX] or None on Cancel
    """

    # If there are no choices, don't ask
    for dev, ssids in devssids.items():
        if len(ssids) > 1:
            break
    else:
        return devssids

    rv = {}
    dialog = gtk.Dialog(_("Select APs"))
    dialog.add_button('gtk-cancel', gtk.RESPONSE_CANCEL)
    dialog.add_button('gtk-ok', 1)
    dialog.set_position(gtk.WIN_POS_CENTER)
    gui.addFrame(dialog)

    dialog.vbox.pack_start(gui.WrappingLabel(
        _("Select APs for wireless devices")))

    table = gtk.Table(len(devssids), 2)
    table.set_row_spacings(5)
    table.set_col_spacings(5)

    combos = {}
    for i, (dev, ssids) in enumerate(devssids.items()):

        label = gtk.Label(dev)
        table.attach(label, 0, 1, i, i+1, gtk.FILL, gtk.FILL)

        combo = gtk.combo_box_new_text()
        for ssid in ssids:
            combo.append_text(ssid)
        table.attach(combo, 1, 2, i, i+1, gtk.FILL, gtk.FILL)
        combo.set_active(0)
        combos[dev] = combo

    dialog.vbox.pack_start(table)

    dialog.show_all()

    rc = dialog.run()

    # cancel
    if rc in [gtk.RESPONSE_CANCEL, gtk.RESPONSE_DELETE_EVENT]:
        rv = None
    else:
        for dev, combo in combos.items():
            rv[dev] = [combo.get_active_text()]

    dialog.destroy()
    return rv


