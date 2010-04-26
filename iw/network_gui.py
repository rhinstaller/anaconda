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
import gui
import network
import iutil
import gobject
import subprocess
import gtk
import isys
import urlgrabber.grabber

from constants import *
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

        self.xml.get_widget("netconfButton").connect("clicked", self._setupNetwork)

        # pressing Enter in confirm == clicking Next
        self.hostnameEntry.connect("activate",
                                   lambda w: self.ics.setGrabNext(1))

        # load the icon
        gui.readImageFromFile("network.png", image=self.icon)

        return self.align

    def _setupNetwork(self, *args):
        self.intf.enableNetwork(just_setup=True)
        if network.hasActiveNetDev():
            urlgrabber.grabber.reset_curl_obj()

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

        self.anaconda.network.hostname = hostname
        return None

def NMCEExited(pid, condition, anaconda):
    if anaconda:
        anaconda.intf.icw.window.set_sensitive(True)

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

def selectNetDevicesDialog(network, select_install_device=True):

    netdevs = network.netdevices
    devs = netdevs.keys()
    devs.sort()

    rv = {}
    dialog = gtk.Dialog(_("Select network interfaces"))
    dialog.add_button('gtk-cancel', gtk.RESPONSE_CANCEL)
    dialog.add_button('gtk-ok', 1)
    dialog.set_position(gtk.WIN_POS_CENTER)
    gui.addFrame(dialog)

    if select_install_device:

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
            ksdevice = ksdevice.get('DEVICE')
        selected_interface_idx = 0

        for idx, dev in enumerate(devs):
            i = store.append(None)

            desc = netdevs[dev].description
            if desc:
                desc = "%s - %s" %(dev, desc)
            else:
                desc = "%s" %(dev,)

            hwaddr = netdevs[dev].get("HWADDR")

            if hwaddr:
                desc = "%s - %s" %(desc, hwaddr,)

            if ksdevice and ksdevice == dev:
                selected_interface_idx = idx

            store[i] = (desc, dev)

        # TODORV: simplify to use just indexes
        combo.set_active(selected_interface_idx)

        def installDevChanged(combo, dev_check_buttons):
            active = combo.get_active()
            for idx, (dev, cb) in enumerate(dev_check_buttons):
                if idx == active:
                    cb.set_active(True)
                    cb.set_sensitive(False)
                else:
                    cb.set_sensitive(True)

        dialog.vbox.pack_start(combo)


    dialog.vbox.pack_start(gui.WrappingLabel(
        _("Select which devices should be configured with NetworkManager.")))

    table = gtk.Table(len(devs), 1)
    table.set_row_spacings(5)
    table.set_col_spacings(5)

    dev_check_buttons = []
    for i, dev in enumerate(devs):
        cb = gtk.CheckButton(dev)
        # TODORV: We want all devices controlled by nm by default,
        # but we might want to add storage net devices filtering here
        #if not (netdevs[dev].get("NM_CONTROLLED") == "no"):
        cb.set_active(True)
        table.attach(cb, 0, 1, i, i+1, gtk.FILL, gtk.FILL)
        dev_check_buttons.append([dev, cb])

    dialog.vbox.pack_start(table)

    if select_install_device:
        selected_dev_cb = dev_check_buttons[selected_interface_idx][1]
        selected_dev_cb.set_active(True)
        selected_dev_cb.set_sensitive(False)
        combo.connect("changed", installDevChanged, dev_check_buttons)

    dialog.show_all()

    rc = dialog.run()

    if rc in [gtk.RESPONSE_CANCEL, gtk.RESPONSE_DELETE_EVENT]:
        retval = None
    else:
        install_device = None
        if select_install_device:
            active = combo.get_active_iter()
            install_device = combo.get_model().get_value(active, 1)

        nm_controlled_devices = [dev for (dev, cb) in dev_check_buttons if
                                 cb.get_active()]

        retval = (nm_controlled_devices, install_device)

    dialog.destroy()
    return retval



