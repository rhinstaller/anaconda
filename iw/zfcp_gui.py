#
# zfcp_gui.py: mainframe FCP configuration dialog
#
# Karsten Hopp <karsten@redhat.com>
#
# Copyright 2000-2006 Red Hat, Inc.
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
import copy

class ZFCPWindow(InstallWindow):

    windowTitle = N_("ZFCP Configuration")

    def __init__(self, ics):
        InstallWindow.__init__(self, ics)

    def getNext(self):
        self.fcp.fcpdevices = self.fcpdevices
        self.fcp.updateConfig(self.fcpdevices, self.diskset, self.intf)

    def setupDevices(self):
        def sortFcpDevs(one, two):
            if one[0] < two[0]:
                return -1
            elif one[0] > two[0]:
                return 1
            return 0
        
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
                column.set_clickable(False)
                column.set_min_width(140)
                column.set_sizing (gtk.TREE_VIEW_COLUMN_AUTOSIZE)
                self.view.append_column(column)
        self.fcpdevices.sort(sortFcpDevs)
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
    def getScreen(self, anaconda):
        self.diskset = anaconda.id.diskset
        self.intf = anaconda.intf
        self.options = anaconda.id.zfcp.options
        box = gtk.VBox(False)
        box.set_border_width(6)
        fcp.cleanFcpSysfs(fcp.fcpdevices)
        self.fcp = ancaonda.id.zfcp
        self.fcpdevices = copy.copy(self.fcp.fcpdevices)
        
        devvbox = gtk.VBox(False)

        self.devlist = self.setupDevices()

        devlistSW = gtk.ScrolledWindow()
        devlistSW.set_border_width(6)
        devlistSW.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        devlistSW.set_shadow_type(gtk.SHADOW_IN)
        devlistSW.add(self.devlist)
        devlistSW.set_size_request(-1, 350)
        devvbox.pack_start(devlistSW, False, padding=10)

        buttonbar = gtk.HButtonBox()
        buttonbar.set_layout(gtk.BUTTONBOX_START)
        buttonbar.set_border_width(6)
        add = gtk.Button(_("_Add"))
        add.connect("clicked", self.addDevice)
        buttonbar.pack_start(add, False)
        edit = gtk.Button(_("_Edit"))
        edit.connect("clicked", self.editDevice)
        buttonbar.pack_start(edit, False)
        remove = gtk.Button(_("_Remove"))
        remove.connect("clicked", self.removeDevice)
        buttonbar.pack_start(remove, False)
        devvbox.pack_start(buttonbar, False)

        devvbox.set_border_width(12)
        l = gtk.Label()
        l.set_markup("<b>%s</b>" %(_("FCP Devices"),))
        frame=gtk.Frame()
        frame.set_label_widget(l)
        frame.add(devvbox)
        frame.set_shadow_type(gtk.SHADOW_NONE)
        box.pack_start(frame, False)
        return box

    def addDevice(self, data):
        if self.ignoreEvents:
            return
        addWin = gtk.Dialog(_("Add FCP device"),
                             flags=gtk.DIALOG_MODAL)
        gui.addFrame(addWin)
        addWin.set_modal(True)
        addWin.set_position (gtk.WIN_POS_CENTER)
        devbox = gtk.VBox()
        fcpTable = gtk.Table(len(self.options), 2)
        entrys = {}
        for t in range(len(self.options)):
            label = gtk.Label("%s:" %(self.options[t][0],))
            label.set_alignment(0.0, 0.5)
            label.set_property("use-underline", True)
            fcpTable.attach(label, 0, 1, t, t+1, gtk.FILL, 0, 10)
            entrys[t] = gtk.Entry(18)
            fcpTable.attach(entrys[t], 1, 2, t, t+1, gtk.FILL, 0, 10)

        devbox.pack_start(fcpTable, False, False, 6)
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
                    tmpvals[t] = self.options[t][3](tmpvals[t])   # sanitize input
                    if tmpvals[t] is not None:                    # update text
                        entrys[t].set_text(tmpvals[t])
                    if self.options[t][4](tmpvals[t]) == -1:      # validate input
                        self.intf.messageWindow(_("Error With Data"),
                            self.options[t][2])
                        invalid = 1
                        break
                        
                if invalid == 0:
                    addWin.destroy()
                    self.store.append(None, (tmpvals[0],tmpvals[1],tmpvals[2],tmpvals[3],tmpvals[4]))
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

        # create dialog box
        editWin = gtk.Dialog(_("Edit FCP device %s") % (devicenum,),
                             flags=gtk.DIALOG_MODAL)
        gui.addFrame(editWin)
        editWin.set_modal(True)
        editWin.set_position (gtk.WIN_POS_CENTER)
        devbox = gtk.VBox()
        fcpTable = gtk.Table(len(self.options), 2)
        entrys = {}
        for t in range(len(self.options)):
            label = gtk.Label("%s:" %(self.options[t][0],))
            label.set_alignment(0.0, 0.5)
            label.set_property("use-underline", True)
            fcpTable.attach(label, 0, 1, t, t+1, gtk.FILL, 0, 10)
            entrys[t] = gtk.Entry(18)
            entrys[t].set_text(model.get_value(iter, t))
            fcpTable.attach(entrys[t], 1, 2, t, t+1, gtk.FILL, 0, 10)
        devbox.pack_start(fcpTable, False, False, 6)
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
                    tmpvals[t] = self.options[t][3](tmpvals[t])   # sanitize input
                    if self.options[t][4](tmpvals[t]) == -1:      # validate input
                        self.intf.messageWindow(_("Error With Data"),
                            self.options[t][2])
                        invalid = 1
                        break
                if invalid == 0:
                    editWin.destroy()
                    for i in range(0, len(self.fcpdevices)):
                        if self.fcpdevices[i][0] == devicenum:
                            break
                    if  (i >= len(self.fcpdevices)):
                        raise ValueError, "Unable to find device: %s" %(devicenum,)
                    
                    for t in range(len(self.options)):
                        self.store.set_value(iter, t, tmpvals[t])
                        self.fcpdevices[i][t] = tmpvals[t]

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
            devicenum = model.get_value(iter, 0)
            for i in range(0, len(self.fcpdevices)):
                if self.fcpdevices[i][0] == devicenum:
                    break
            if  (i >= len(self.fcpdevices)):
                raise ValueError, "Unable to find device: %s" %(devicenum,)
            self.fcpdevices.pop(i)
            self.store.remove(iter)
            
        return

# vim:tw=78:ts=4:et:sw=4
