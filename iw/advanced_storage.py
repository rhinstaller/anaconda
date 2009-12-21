#
# Copyright (C) 2009  Red Hat, Inc.  All rights reserved.
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

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

# UI methods for supporting adding advanced storage devices.
import gobject
import gtk
import gtk.glade
import gui
import iutil
import network
import storage.fcoe
import storage.iscsi
from netconfig_dialog import NetworkConfigurator

def addFcoeDrive(anaconda):
    (dxml, dialog) = gui.getGladeWidget("fcoe-config.glade", "fcoeDialog")
    combo = dxml.get_widget("fcoeNicCombo")
    dcb_cb = dxml.get_widget("dcbCheckbutton")

    # Populate the combo
    cell = gtk.CellRendererText()
    combo.pack_start(cell, True)
    combo.set_attributes(cell, text = 0)
    cell.set_property("wrap-width", 525)
    combo.set_size_request(480, -1)
    store = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
    combo.set_model(store)

    netdevs = anaconda.network.available()
    keys = netdevs.keys()
    keys.sort()
    selected_interface = None
    for dev in keys:
        # Skip NICs which are connected (iow in use for a net install)
        if dev in network.getActiveNetDevs():
            continue

        i = store.append(None)
        desc = netdevs[dev].get("DESC")
        if desc:
            desc = "%s - %s" %(dev, desc)
        else:
            desc = "%s" %(dev,)

        mac = netdevs[dev].get("HWADDR")
        if mac:
            desc = "%s - %s" %(desc, mac)

        if selected_interface is None:
            selected_interface = i

        store[i] = (desc, dev)

    if selected_interface:
        combo.set_active_iter(selected_interface)
    else:
        combo.set_active(0)

    # Show the dialog
    gui.addFrame(dialog)
    dialog.show_all()
    sg = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
    sg.add_widget(dxml.get_widget("fcoeNicCombo"))

    while True:
        rc = dialog.run()

        if rc in [gtk.RESPONSE_CANCEL, gtk.RESPONSE_DELETE_EVENT]:
            break

        iter = combo.get_active_iter()
        if iter is None:
            anaconda.intf.messageWindow(_("Error"),
                                        _("You must select a NIC to use."),
                                        type="warning", custom_icon="error")
            continue

        try:
            anaconda.storage.fcoe.addSan(store.get_value(iter, 1),
                                         dcb=dcb_cb.get_active(),
                                         intf=anaconda.intf)
        except IOError as e:
            anaconda.intf.messageWindow(_("Error"), str(e))
            rc = gtk.RESPONSE_CANCEL

        break

    dialog.destroy()
    return rc

def addIscsiDrive(anaconda):
    if not network.hasActiveNetDev():
        net = NetworkConfigurator(anaconda.network)
        ret = net.run()
        net.destroy()
        if ret != gtk.RESPONSE_OK:
            return ret

    (dxml, dialog) = gui.getGladeWidget("iscsi-config.glade", "iscsiDialog")
    gui.addFrame(dialog)
    dialog.show_all()
    sg = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
    for w in ["iscsiAddrEntry", "iscsiInitiatorEntry", "userEntry",
              "passEntry", "userinEntry", "passinEntry"]:
        sg.add_widget(dxml.get_widget(w))

    # get the initiator name if it exists and don't allow changing
    # once set
    e = dxml.get_widget("iscsiInitiatorEntry")
    e.set_text(anaconda.storage.iscsi.initiator)
    if anaconda.storage.iscsi.initiatorSet:
        e.set_sensitive(False)

    while True:
        rc = dialog.run()
        if rc in [gtk.RESPONSE_CANCEL, gtk.RESPONSE_DELETE_EVENT]:
            break

        initiator = e.get_text().strip()
        if len(initiator) == 0:
            anaconda.intf.messageWindow(_("Invalid Initiator Name"),
                                        _("You must provide an initiator name."))
            continue

        anaconda.storage.iscsi.initiator = initiator

        target = dxml.get_widget("iscsiAddrEntry").get_text().strip()
        user = dxml.get_widget("userEntry").get_text().strip()
        pw = dxml.get_widget("passEntry").get_text().strip()
        user_in = dxml.get_widget("userinEntry").get_text().strip()
        pw_in = dxml.get_widget("passinEntry").get_text().strip()

        try:
            count = len(target.split(":"))
            idx = target.rfind("]:")
            # Check for IPV6 [IPV6-ip]:port
            if idx != -1:
                ip = target[1:idx]
                port = target[idx+2:]
            # Check for IPV4 aaa.bbb.ccc.ddd:port
            elif count == 2:
                idx = target.rfind(":")
                ip = target[:idx]
                port = target[idx+1:]
            else:
                ip = target
                port = "3260"

            network.sanityCheckIPString(ip)
        except (network.IPMissing, network.IPError) as msg:
            anaconda.intf.messageWindow(_("Error with Data"), msg)
            continue

        try:
            anaconda.storage.iscsi.addTarget(ip, port, user, pw,
                                             user_in, pw_in,
                                             anaconda.intf)
        except ValueError as e:
            anaconda.intf.messageWindow(_("Error"), str(e))
            continue
        except IOError as e:
            anaconda.intf.messageWindow(_("Error"), str(e))
            rc = gtk.RESPONSE_CANCEL

        break

    dialog.destroy()
    return rc

def addZfcpDrive(anaconda):
    (dxml, dialog) = gui.getGladeWidget("zfcp-config.glade", "zfcpDialog")
    gui.addFrame(dialog)
    dialog.show_all()
    sg = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
    for w in ["devnumEntry", "wwpnEntry", "fcplunEntry"]:
        sg.add_widget(dxml.get_widget(w))

    while True:
        rc = dialog.run()
        if rc != gtk.RESPONSE_APPLY:
            break

        devnum = dxml.get_widget("devnumEntry").get_text().strip()
        wwpn = dxml.get_widget("wwpnEntry").get_text().strip()
        fcplun = dxml.get_widget("fcplunEntry").get_text().strip()

        try:
            anaconda.storage.zfcp.addFCP(devnum, wwpn, fcplun)
        except ValueError as e:
            anaconda.intf.messageWindow(_("Error"), str(e))
            continue

        break

    dialog.destroy()
    return rc

def addDrive(anaconda):
    (dxml, dialog) = gui.getGladeWidget("adddrive.glade", "addDriveDialog")
    gui.addFrame(dialog)
    dialog.show_all()
    if not iutil.isS390():
        dxml.get_widget("zfcpRadio").hide()
        dxml.get_widget("zfcpRadio").set_group(None)

    if not storage.iscsi.has_iscsi():
        dxml.get_widget("iscsiRadio").set_sensitive(False)
        dxml.get_widget("iscsiRadio").set_active(False)

    if not storage.fcoe.has_fcoe():
        dxml.get_widget("fcoeRadio").set_sensitive(False)
        dxml.get_widget("fcoeRadio").set_active(False)

    #figure out what advanced devices we have available and set sensible default
    group = dxml.get_widget("iscsiRadio").get_group()
    for button in group:
        if button is not None and button.get_property("sensitive"):
            button.set_active(True)
            break

    rc = dialog.run()
    dialog.hide()

    if rc in [gtk.RESPONSE_CANCEL, gtk.RESPONSE_DELETE_EVENT]:
        return False

    if dxml.get_widget("iscsiRadio").get_active() and storage.iscsi.has_iscsi():
        rc = addIscsiDrive(anaconda)
    elif dxml.get_widget("fcoeRadio").get_active() and storage.fcoe.has_fcoe():
        rc = addFcoeDrive(anaconda)
    elif dxml.get_widget("zfcpRadio") is not None and dxml.get_widget("zfcpRadio").get_active():
        rc = addZfcpDrive(anaconda)

    dialog.destroy()

    if rc in [gtk.RESPONSE_CANCEL, gtk.RESPONSE_DELETE_EVENT]:
        return False
    else:
        return True
