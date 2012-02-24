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
import datacombo
import DeviceSelector
import functools
import gobject
import gtk
import gtk.glade
import gui
import iutil
import network
import partIntfHelpers as pih
import storage.fcoe
import storage.iscsi
import urlgrabber.grabber

import logging
log = logging.getLogger("anaconda")

class iSCSICredentialsDialog(object):
    def __init__(self):
        pass

    def _authentication_kind_changed(self,
                                     combobox,
                                     credentials,
                                     rev_credentials):
        active_value = combobox.get_active_value()
        if active_value in [pih.CRED_NONE[0], pih.CRED_REUSE[0]]:
            map(lambda w : w.hide(), credentials)
            map(lambda w : w.hide(), rev_credentials)
        elif active_value == pih.CRED_ONE[0]:
            map(lambda w : w.show(), credentials)
            map(lambda w : w.hide(), rev_credentials)
        elif active_value == pih.CRED_BOTH[0]:
            map(lambda w : w.show(), credentials)
            map(lambda w : w.show(), rev_credentials)

    def _combo_box(self, entries, credentials, rev_credentials):
        combo_store = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_INT)
        combo = datacombo.DataComboBox(store=combo_store)
        for entry in entries:
            combo.append(entry[1], entry[0])
        if len(entries) > 0:
            combo.set_active(0)
        combo.show_all()
        combo.connect("changed", 
                      self._authentication_kind_changed, 
                      credentials,
                      rev_credentials)
        return combo

    def _credentials_widgets(self, xml):
        credentials = [xml.get_widget(w_name) for w_name in 
                       ['username_label',
                        'username_entry',
                        'password_label', 
                        'password_entry']]
        rev_credentials = [xml.get_widget(w_name) for w_name in 
                           ['r_username_label',
                            'r_username_entry',
                            'r_password_label', 
                            'r_password_entry']]
        return (credentials, rev_credentials)
    
    def _extract_credentials(self, xml):
        return {
            'username'   : xml.get_widget("username_entry").get_text(),
            'password'   : xml.get_widget("password_entry").get_text(),
            'r_username' : xml.get_widget("r_username_entry").get_text(),
            'r_password' : xml.get_widget("r_password_entry").get_text()
        }

class iSCSIDiscoveryDialog(iSCSICredentialsDialog):

    def __init__(self, initiator, initiator_set):
        super(iSCSIDiscoveryDialog, self).__init__()
        (self.xml, self.dialog) = gui.getGladeWidget("iscsi-dialogs.glade", "discovery_dialog")

        self.initiator = self.xml.get_widget("initiator")
        self.initiator.set_text(initiator)
        if initiator_set:
            self.initiator.set_sensitive(False)

        (credentials, rev_credentials) = self._credentials_widgets(self.xml)
        self.combobox = self._combo_box([
                pih.CRED_NONE,
                pih.CRED_ONE,
                pih.CRED_BOTH,
                ], credentials, rev_credentials)
        vbox = self.xml.get_widget("d_discovery_vbox")
        vbox.pack_start(self.combobox, expand=False)

    def discovery_dict(self):
        dct = self._extract_credentials(self.xml)

        auth_kind = self.combobox.get_active_value()
        if auth_kind == pih.CRED_NONE[0]:
            dct["username"] = dct["password"] = \
                dct["r_username"] = dct["r_password"] = None
        elif auth_kind == pih.CRED_ONE[0]:
            dct["r_username"] = dct["r_password"] = None

        entered_ip = self.xml.get_widget("target_ip").get_text()
        (ip, port) = pih.parse_ip(entered_ip)
        dct["ipaddr"] = ip
        dct["port"]   = port
        
        return dct

    def get_initiator(self):
        return self.initiator.get_text()

class iSCSILoginDialog(iSCSICredentialsDialog):

    def __init__(self):
        super(iSCSILoginDialog, self).__init__()
        (xml, self.dialog) = gui.getGladeWidget("iscsi-dialogs.glade", "login_dialog")
        # take credentials from the discovery dialog
        (self.credentials_xml, credentials_table) = gui.getGladeWidget("iscsi-dialogs.glade", "table_credentials")
        (credentials, rev_credentials) = self._credentials_widgets(self.credentials_xml)
        # and put them into the login dialog alignment
        alignment = xml.get_widget("login_credentials_alignment")
        alignment.add(credentials_table)
        # setup the combobox
        self.combobox = self._combo_box([
                pih.CRED_NONE,
                pih.CRED_ONE,
                pih.CRED_BOTH,
                pih.CRED_REUSE
                ], credentials, rev_credentials)
        vbox = xml.get_widget("d_login_vbox")
        vbox.pack_start(self.combobox, expand=False)

    def login_dict(self, discovery_dict):
        dct = self._extract_credentials(self.credentials_xml)

        auth_kind = self.combobox.get_active_value()
        if auth_kind == pih.CRED_NONE[0]:
            dct["username"] = dct["password"] = \
                dct["r_username"] = dct["r_password"] = None
        elif auth_kind == pih.CRED_ONE[0]:
            dct["r_username"] = dct["r_password"] = None
        elif auth_kind == pih.CRED_REUSE[0]:
            # only keep what we'll really use:
            discovery_dict = dict((k,discovery_dict[k]) for k in discovery_dict if k in 
                                  ['username', 
                                   'password', 
                                   'r_username', 
                                   'r_password'])
            dct.update(discovery_dict)

        return dct

class iSCSIGuiWizard(pih.iSCSIWizard):
    NODE_NAME_COL = DeviceSelector.IMMUTABLE_COL + 1
    NODE_INTERFACE_COL = DeviceSelector.IMMUTABLE_COL + 2

    def __init__(self):
        self.login_dialog = None
        self.discovery_dialog = None
        
    def _destroy_when_dialog(self, dialog):
        if dialog and dialog.dialog:
            dialog.dialog.destroy()

    def _normalize_dialog_response(self, value):
        """
        Maps the glade return values to a boolean.

        Returns True upon success.
        """
        if value == 1: 
            # gtk.RESPONSE_OK
            return True 
        elif value == -6:
            # gtk.RESPONSE_CANCEL
            return False 
        elif value == gtk.RESPONSE_DELETE_EVENT: 
            # escape pressed to dismiss the dialog
            return False
        else:
            raise ValueError("Unexpected dialog box return value: %d" % value)
        
    def _run_dialog(self, dialog):
        gui.addFrame(dialog)
        dialog.show()
        rc = dialog.run()
        dialog.hide()
        return self._normalize_dialog_response(rc)
    
    def destroy_dialogs(self):
        self._destroy_when_dialog(self.discovery_dialog)
        self._destroy_when_dialog(self.login_dialog)
    
    def display_discovery_dialog(self, initiator, initiator_set):
        self._destroy_when_dialog(self.discovery_dialog)
        self.discovery_dialog = iSCSIDiscoveryDialog(initiator, initiator_set)

        return self._run_dialog(self.discovery_dialog.dialog)

    def display_login_dialog(self):
        self._destroy_when_dialog(self.login_dialog)
        self.login_dialog = iSCSILoginDialog()

        return self._run_dialog(self.login_dialog.dialog)

    def display_nodes_dialog(self, found_nodes, ifaces):
        def _login_button_disabler(device_selector, login_button, checked, item):
            login_button.set_sensitive(len(device_selector.getSelected()) > 0)

        (xml, dialog) = gui.getGladeWidget("iscsi-dialogs.glade", "nodes_dialog")
        store = gtk.TreeStore(
            gobject.TYPE_PYOBJECT, # teh object
            gobject.TYPE_BOOLEAN,  # visible
            gobject.TYPE_BOOLEAN,  # active (checked)
            gobject.TYPE_BOOLEAN,  # immutable
            gobject.TYPE_STRING,   # node name
            gobject.TYPE_STRING    # node interface
            )
        map(lambda node : store.append(None, (
                    node,        # the object
                    True,        # visible
                    True,        # active
                    False,       # not immutable
                    node.name,   # node's name
                    ifaces.get(node.iface, node.iface))), # node's interface
            found_nodes)

        # create and setup the device selector
        model = store.filter_new()
        view = gtk.TreeView(model)
        ds = DeviceSelector.DeviceSelector(
            store,
            model,
            view)
        callback = functools.partial(_login_button_disabler,
                                     ds,
                                     xml.get_widget("button_login"))
        ds.createSelectionCol(toggledCB=callback)
        ds.addColumn(_("Node Name"), self.NODE_NAME_COL)
        ds.addColumn(_("Interface"), self.NODE_INTERFACE_COL)
        # attach the treeview to the dialog
        sw = xml.get_widget("nodes_scrolled_window")
        sw.add(view)
        sw.show_all()

        # run the dialog
        rc = self._run_dialog(dialog)
        # filter out selected nodes:
        selected_nodes = map(lambda raw : raw[0], ds.getSelected())
        dialog.destroy()
        return (rc, selected_nodes)

    def display_success_dialog(self, success_nodes, fail_nodes, fail_reason,
                               ifaces):
        (xml, dialog) = gui.getGladeWidget("iscsi-dialogs.glade", "success_dialog")
        w_success = xml.get_widget("label_success")
        w_success_win = xml.get_widget("scroll_window_success")
        w_success_val = xml.get_widget("text_success")
        w_fail = xml.get_widget("label_fail")
        w_fail_win = xml.get_widget("scroll_window_fail")
        w_fail_val = xml.get_widget("text_fail")
        w_reason = xml.get_widget("label_reason")
        w_reason_val = xml.get_widget("label_reason_val")
        w_retry = xml.get_widget("button_retry")
        w_separator = xml.get_widget("separator")

        if success_nodes:
            markup = "\n".join(map(lambda n: "%s via %s" % (n.name, ifaces.get(n.iface, n.iface)), success_nodes))
            buf = gtk.TextBuffer()
            buf.set_text(markup)
            w_success.show()
            w_success_val.set_buffer(buf)
            w_success_win.show()
        if fail_nodes:
            markup = "\n".join(map(lambda n: "%s via %s" % (n.name, ifaces.get(n.iface, n.iface)), fail_nodes))
            buf = gtk.TextBuffer()
            buf.set_text(markup)
            w_fail.show()
            w_fail_val.set_buffer(buf)
            w_fail_win.show()
            w_retry.show()
        if fail_reason:
            w_reason.show()
            w_reason_val.set_markup(fail_reason)
            w_reason_val.show()
        if success_nodes and fail_nodes:
            # only if there's anything to be separated display the separator
            w_separator.show()
        
        rc = self._run_dialog(dialog)
        dialog.destroy()
        return rc
    
    def get_discovery_dict(self):
        return self.discovery_dialog.discovery_dict()

    def get_initiator(self):
        return self.discovery_dialog.get_initiator()
    
    def get_login_dict(self):
        return self.login_dialog.login_dict(self.get_discovery_dict())
    
    def set_initiator(self, initiator, initiator_set):
        (self.initiator, self.initiator_set) = initiator, initiator_set

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

    netdevs = anaconda.id.network.netdevices
    keys = netdevs.keys()
    keys.sort()
    selected_interface = None
    for dev in keys:
        i = store.append(None)
        desc = netdevs[dev].description
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
        # make sure the dialog pops into foreground in case this is the second
        # time through the loop:
        dialog.present()
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
            anaconda.id.storage.fcoe.addSan(store.get_value(iter, 1),
                                            dcb=dcb_cb.get_active(),
                                            intf=anaconda.intf)
        except IOError as e:
            anaconda.intf.messageWindow(_("Error"), str(e))
            rc = gtk.RESPONSE_CANCEL

        break

    dialog.destroy()
    return rc

def addIscsiDrive(anaconda, bind=False):
    """
    Displays a series of dialogs that walk the user through discovering and
    logging into iscsi nodes.
    
    Returns gtk.RESPONSE_OK if at least one iscsi node has been logged into.
    """

    # make sure the network is up
    if not network.hasActiveNetDev():
        if not anaconda.intf.enableNetwork():
            log.info("addIscsiDrive(): early exit, network disabled.")
            return gtk.RESPONSE_CANCEL
        urlgrabber.grabber.reset_curl_obj()

    # This will modify behaviour of iscsi.discovery() function
    if storage.iscsi.iscsi().mode == "none" and not bind:
        storage.iscsi.iscsi().delete_interfaces()
    elif (storage.iscsi.iscsi().mode == "none" and bind) \
          or storage.iscsi.iscsi().mode == "bind":
        active = set(network.getActiveNetDevs())
        created = set(storage.iscsi.iscsi().ifaces.values())
        storage.iscsi.iscsi().create_interfaces(active - created)

    wizard = iSCSIGuiWizard()
    login_ok_nodes = pih.drive_iscsi_addition(anaconda, wizard)
    if len(login_ok_nodes):
        return gtk.RESPONSE_OK
    log.info("addIscsiDrive(): no new nodes added")
    return gtk.RESPONSE_CANCEL

def addZfcpDrive(anaconda):
    (dxml, dialog) = gui.getGladeWidget("zfcp-config.glade", "zfcpDialog")
    gui.addFrame(dialog)
    dialog.show_all()
    sg = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
    for w in ["devnumEntry", "wwpnEntry", "fcplunEntry"]:
        sg.add_widget(dxml.get_widget(w))

    while True:
        dialog.present()
        rc = dialog.run()
        if rc != gtk.RESPONSE_APPLY:
            break

        devnum = dxml.get_widget("devnumEntry").get_text().strip()
        wwpn = dxml.get_widget("wwpnEntry").get_text().strip()
        fcplun = dxml.get_widget("fcplunEntry").get_text().strip()

        try:
            anaconda.id.storage.zfcp.addFCP(devnum, wwpn, fcplun)
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
        dxml.get_widget("iscsiBindCheck").set_sensitive(False)
    else:
        dxml.get_widget("iscsiBindCheck").set_active(bool(storage.iscsi.iscsi().ifaces))
        dxml.get_widget("iscsiBindCheck").set_sensitive(storage.iscsi.iscsi().mode == "none")

    if not storage.fcoe.has_fcoe():
        dxml.get_widget("fcoeRadio").set_sensitive(False)
        dxml.get_widget("fcoeRadio").set_active(False)

    def update_active_ifaces():
        active_ifaces = network.getActiveNetDevs()
        dxml.get_widget("ifaceLabel").set_text(", ".join(active_ifaces))

    def netconfButton_clicked(*args):
        from network_gui import setupNetwork
        setupNetwork(anaconda.intf)
        update_active_ifaces()

    dxml.get_widget("netconfButton").connect("clicked", netconfButton_clicked)
    update_active_ifaces()

    #figure out what advanced devices we have available and set sensible default
    group = dxml.get_widget("iscsiRadio").get_group()
    for button in group:
        if button is not None and button.get_property("sensitive"):
            button.set_active(True)
            button.grab_focus()
            break

    rc = dialog.run()
    dialog.hide()

    if rc in [gtk.RESPONSE_CANCEL, gtk.RESPONSE_DELETE_EVENT]:
        return False

    if dxml.get_widget("iscsiRadio").get_active() and storage.iscsi.has_iscsi():
        bind = dxml.get_widget("iscsiBindCheck").get_active()
        rc = addIscsiDrive(anaconda, bind)
    elif dxml.get_widget("fcoeRadio").get_active() and storage.fcoe.has_fcoe():
        rc = addFcoeDrive(anaconda)
    elif dxml.get_widget("zfcpRadio") is not None and dxml.get_widget("zfcpRadio").get_active():
        rc = addZfcpDrive(anaconda)

    dialog.destroy()

    if rc in [gtk.RESPONSE_CANCEL, gtk.RESPONSE_DELETE_EVENT]:
        return False
    else:
        return True
