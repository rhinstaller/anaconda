#
# zfcp_gui.py: mainframe FCP configuration dialog
#
# Karsten Hopp <karsten@redhat.com>
#
# Copyright 2000-2004 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
import gtk
import gobject
from iw_gui import *
import gui
from rhpl.translate import _, N_
import os
import isys
import iutil

class ZFCPWindow(InstallWindow):

    windowTitle = N_("ZFCP Configuration")
    htmlTag = "zfcpconf"

    def __init__(self, ics):
        InstallWindow.__init__(self, ics)
        self.options = [(_("Device number"), 1, self.handleInvalidDevice),
                        (_("SCSI Id"),       0, self.handleInvalidSCSIId),
                        (_("WWPN"),          1, self.handleInvalidWWPN),
                        (_("SCSI LUN"),      0, self.handleInvalidSCSILun),
                        (_("FCP LUN"),       1, self.handleInvalidFCPLun)]

    def getNext(self):
        self.fcp.writeFcpSysfs(self.fcpdevices)
        isys.flushDriveDict()
        self.diskset.refreshDevices(self.intf)
        try:
            iutil.makeDriveDeviceNodes()
        except:
            pass

    def handleInvalidDevice(self):
        self.intf.messageWindow(_("Error With Data"),
        _("You have not specified a device number or the number is invalid"))

    def handleInvalidSCSIId(self):
        self.intf.messageWindow(_("Error With Data"),
            _("You have not specified a SCSI ID or the ID is invalid."))

    def handleInvalidWWPN(self):
        self.intf.messageWindow(_("Error With Data"),
            _("You have not specified a worldwide port name or the name is invalid."))

    def handleInvalidSCSILun(self):
        self.intf.messageWindow(_("Error With Data"),
            _("You have not specified a SCSI LUN or the number is invalid."))

    def handleInvalidFCPLun(self):
        self.intf.messageWindow(_("Error With Data"),
            _("You have not specified a FCP LUN or the number is invalid."))

    def setupDevices(self):
        self.store = gtk.TreeStore(gobject.TYPE_STRING,
                                   gobject.TYPE_STRING,
                                   gobject.TYPE_STRING,
                                   gobject.TYPE_STRING,
                                   gobject.TYPE_STRING)

        self.view = gtk.TreeView(self.store)
        for i in range(len(self.options)):
            if self.options[i][1] == 1:
                renderer = gtk.CellRendererText()
                column = gtk.TreeViewColumn(self.options[i][0], renderer, text=i)
                column.set_clickable(gtk.FALSE)
                column.set_min_width(140)
                column.set_sizing (gtk.TREE_VIEW_COLUMN_AUTOSIZE)
                self.view.append_column(column)
        for i in range(len(self.fcpdevices)):
            self.store.append(None, (self.fcpdevices[i][0],self.fcpdevices[i][1], \
              self.fcpdevices[i][2],self.fcpdevices[i][3],self.fcpdevices[i][4]))

        self.ignoreEvents = 1
        iter = self.store.get_iter_first()
        selection = self.view.get_selection()
        selection.set_mode(gtk.SELECTION_BROWSE)
        if iter != None:
            selection.select_iter(iter)
        self.ignoreEvents = 0
        return self.view


    # ZFCPWindow tag="zfcpconf"
    def getScreen(self, fcp, diskset, intf):
        self.diskset = diskset
        self.intf = intf
        box = gtk.VBox(gtk.FALSE)
        box.set_border_width(6)
        fcp.cleanFcpSysfs(fcp.fcpdevices)
        self.fcp = fcp
        self.fcpdevices = fcp.fcpdevices
        
        devvbox = gtk.VBox(gtk.FALSE)

        self.devlist = self.setupDevices()

        devlistSW = gtk.ScrolledWindow()
        devlistSW.set_border_width(6)
        devlistSW.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        devlistSW.set_shadow_type(gtk.SHADOW_IN)
        devlistSW.add(self.devlist)
        devlistSW.set_size_request(-1, 350)
        devvbox.pack_start(devlistSW, gtk.FALSE, padding=10)

        buttonbar = gtk.HButtonBox()
        buttonbar.set_layout(gtk.BUTTONBOX_START)
        buttonbar.set_border_width(6)
        add = gtk.Button(_("_Add"))
        add.connect("clicked", self.addDevice)
        buttonbar.pack_start(add, gtk.FALSE)
        edit = gtk.Button(_("_Edit"))
        edit.connect("clicked", self.editDevice)
        buttonbar.pack_start(edit, gtk.FALSE)
        remove = gtk.Button(_("_Remove"))
        remove.connect("clicked", self.removeDevice)
        buttonbar.pack_start(remove, gtk.FALSE)
        devvbox.pack_start(buttonbar, gtk.FALSE)

        devvbox.set_border_width(12)
        l = gtk.Label()
        l.set_markup("<b>%s</b>" %(_("FCP Devices"),))
        frame=gtk.Frame()
        frame.set_label_widget(l)
        frame.add(devvbox)
        frame.set_shadow_type(gtk.SHADOW_NONE)
        box.pack_start(frame, gtk.FALSE)
        return box


    def addDevice(self, data):
        if self.ignoreEvents:
            return
        addWin = gtk.Dialog(_("Add FCP device"),
                             flags=gtk.DIALOG_MODAL)
        gui.addFrame(addWin)
        addWin.set_modal(gtk.TRUE)
        addWin.set_position (gtk.WIN_POS_CENTER)
        devbox = gtk.VBox()
        fcpTable = gtk.Table(len(self.options), 2)
        entrys = {}
        for t in range(len(self.options)):
            label = gtk.Label("%s:" %(self.options[t][0],))
            label.set_alignment(0.0, 0.5)
            label.set_property("use-underline", gtk.TRUE)
            fcpTable.attach(label, 0, 1, t, t+1, gtk.FILL, 0, 10)
            entrys[t] = gtk.Entry(18)
            fcpTable.attach(entrys[t], 1, 2, t, t+1, gtk.FILL, 0, 10)

        devbox.pack_start(fcpTable, gtk.FALSE, gtk.FALSE, 6)
        devbox.set_border_width(6)
        frame = gtk.Frame()
        frame.set_border_width(12)
        frame.add(devbox)
        frame.set_shadow_type(gtk.SHADOW_NONE)
        addWin.vbox.pack_start(frame, padding=6)
        addWin.set_position(gtk.WIN_POS_CENTER)
        addWin.show_all()
        addWin.add_button('gtk-cancel', 2)
        addWin.add_button('gtk-ok', 1)
        tmpvals = {}
        while 1:
            invalid = 0
            rc = addWin.run()
            if rc == 1:
                for t in range(len(self.options)):
                    tmpvals[t] = entrys[t].get_text()
                    if tmpvals[t] == "":
                        self.options[t][2]()   # FIXME: This hides addWin behind the main window
                        invalid = 1
                        break
                    if t != 0 and tmpvals[t][:2] != "0x":
                        tmpvals[t] = "0x" + tmpvals[t]
                    elif t == 0:
                        tmpvals[t] = "0" * (4 - len(tmpvals[t])) + tmpvals[t]
                        if tmpvals[t][:4] != "0.0.":
                            tmpvals[t] = "0.0." + tmpvals[t]
                        
                if invalid == 0:
                    addWin.destroy()
                    tmpvals[4] = self.fcp.expandLun(tmpvals[4])
                    line = self.store.append(None, (tmpvals[0],tmpvals[1],tmpvals[2],tmpvals[3],tmpvals[4]))
                    self.fcpdevices.append(tmpvals)
                    break
            if rc == 2:
                addWin.destroy()
                break
        return

    def editDevice(self, data):
        if self.ignoreEvents:
            return
        selection = self.view.get_selection()
        (model, iter) = selection.get_selected()
        if not iter:
            return None
        devicenum = model.get_value(iter, 0)
        scsiid = model.get_value(iter, 1)
        wwpn = model.get_value(iter, 2)
        scsilun = model.get_value(iter, 3)
        fcplun = model.get_value(iter, 4)

        # create dialog box
        editWin = gtk.Dialog(_("Edit FCP device %s") % (devicenum,),
                             flags=gtk.DIALOG_MODAL)
        gui.addFrame(editWin)
        editWin.set_modal(gtk.TRUE)
        editWin.set_position (gtk.WIN_POS_CENTER)
        devbox = gtk.VBox()
        fcpTable = gtk.Table(len(self.options), 2)
        entrys = {}
        for t in range(len(self.options)):
            label = gtk.Label("%s:" %(self.options[t][0],))
            label.set_alignment(0.0, 0.5)
            label.set_property("use-underline", gtk.TRUE)
            fcpTable.attach(label, 0, 1, t, t+1, gtk.FILL, 0, 10)
            entrys[t] = gtk.Entry(18)
            entrys[t].set_text(model.get_value(iter, t))
            fcpTable.attach(entrys[t], 1, 2, t, t+1, gtk.FILL, 0, 10)
        devbox.pack_start(fcpTable, gtk.FALSE, gtk.FALSE, 6)
        devbox.set_border_width(6)
        frame = gtk.Frame()
        frame.set_border_width(12)
        frame.add(devbox)
        frame.set_shadow_type(gtk.SHADOW_NONE)
        editWin.vbox.pack_start(frame, padding=6)
        editWin.set_position(gtk.WIN_POS_CENTER)
        editWin.show_all()
        editWin.add_button('gtk-cancel', 2)
        editWin.add_button('gtk-ok', 1)
        tmpvals = {}
        while 1:
            invalid = 0
            rc = editWin.run()
            if rc == 2:
                editWin.destroy()
                return
            if rc == 1:
                for t in range(len(self.options)):
                    tmpvals[t] = entrys[t].get_text()
                    if tmpvals[t] == "":
                        self.options[t][2]()   # FIXME: This hides addWin behind the main window
                        invalid = 1
                        break
                if invalid == 0:
                    editWin.destroy()
                    for t in range(len(self.options)):
                        self.store.set_value(iter, t, tmpvals[t])
                    break
        return

    def removeDevice(self, data):
        selection = self.view.get_selection()
        (model, iter) = selection.get_selected()
        if not iter:
            return None
        rc = self.intf.messageWindow(_("Warning"),
            _("You're about to remove a FCP disk from your "
              "configuration. Are you sure that you wish "
              "to continue?"), type = "yesno")
        if rc == 1:
            self.store.remove(iter)
        return

# vim:tw=78:ts=4:et:sw=4
