#
# upgrade_swap_gui.py: dialog for adding swap files for 2.4
#
# Mike Fulbright <msf@redhat.com>
#
# Copyright 2001-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import string
import isys 
import iutil
import upgrade
import gui
import gobject
import gtk
from iw_gui import *
from flags import flags

from rhpl.translate import _, N_

class UpgradeSwapWindow (InstallWindow):		
    windowTitle = N_("Upgrade Swap Partition")

    def getNext (self):
        #-If the user doesn't need to add swap, we don't do anything
        if not self.neededSwap:
            return None

        if self.option2.get_active():
            rc = self.warning()

            if rc == 0:
                raise gui.StayOnScreen
            else:
                return None

	selection = self.view.get_selection()
	(model, iter) = selection.get_selected()
	if iter:
	    mnt = model.get_value(iter, 0)
	    part = model.get_value(iter, 1)
	    size = int(model.get_value(iter, 2))
            val = int(self.entry.get_text())
	else:
	    raise RuntimeError, "unknown value for upgrade swap location"

        if val > 2000 or val < 1:
            rc = self.swapWrongSize()
            raise gui.StayOnScreen

        elif (val+16) > size:
            rc = self.swapTooBig()
            raise gui.StayOnScreen            

        else:
            if flags.setupFilesystems:
                upgrade.createSwapFile(self.instPath, self.fsset, mnt, val)
            self.dispatch.skipStep("addswap", 1)
                
        return None

    def toggle (self, data):
        self.swapbox.set_sensitive(self.option1.get_active())

    def clist_cb(self, clist, row, col, data):
        self.row = row
    
    def getScreen (self, anaconda):
        self.neededSwap = 0
        self.fsset = anaconda.id.fsset
        self.instPath = anaconda.rootPath
        self.intf = anaconda.intf
        self.dispatch = anaconda.dispatch
        
        rc = anaconda.id.upgradeSwapInfo

        self.neededSwap = 1
        self.row = 0
        box = gtk.VBox (False, 5)
        box.set_border_width (5)

	label = gtk.Label (_("The 2.4 kernel needs significantly more "
                            "swap than older kernels, as much as twice "
                            "as much swap space as RAM on the system.  "
                            "You currently have %dMB of swap configured, but "
                            "you may create additional swap space on one of "
                            "your file systems now.")
                          % (iutil.swapAmount() / 1024) +
                          _("\n\nThe installer has detected %s MB of RAM.\n") %
                          (iutil.memInstalled()/1024))

        label.set_alignment (0.5, 0.0)
#        label.set_size_request(400, 200)
        label.set_line_wrap (True)
        box.pack_start(label, False)

        hs = gtk.HSeparator()
        box.pack_start(hs, False)

        self.option1 = gtk.RadioButton(None,
                                      (_("I _want to create a swap file")))
        box.pack_start(self.option1, False)

        (fsList, suggSize, suggMntPoint) = rc

        self.swapbox = gtk.VBox(False, 5)
        box.pack_start(self.swapbox, False)
        

        label = gui.MnemonicLabel (_("Select the _partition to put the swap file on:"))
        a = gtk.Alignment(0.2, 0.5)
        a.add(label)
        self.swapbox.pack_start(a, False)

	self.store = gtk.ListStore(gobject.TYPE_STRING,
				   gobject.TYPE_STRING,
				   gobject.TYPE_STRING)

        for (mnt, part, size) in fsList:
	    iter = self.store.append()
	    self.store.set_value(iter, 0, mnt)
	    self.store.set_value(iter, 1, part)
	    self.store.set_value(iter, 2, str(size))

	self.view=gtk.TreeView(self.store)
        label.set_mnemonic_widget(self.view)

	i = 0
	for title in [(_("Mount Point")), (_("Partition")), (_("Free Space (MB)"))]:
	    col = gtk.TreeViewColumn(title, gtk.CellRendererText(), text=i)
	    self.view.append_column(col)
	    i = i + 1

	sw = gtk.ScrolledWindow()
	sw.add(self.view)
	sw.set_shadow_type(gtk.SHADOW_IN)
	sw.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
	sw.set_size_request(300, 90)
	a = gtk.Alignment(0.5, 0.5)
        a.add(sw)
        self.swapbox.pack_start(a, False, True, 10)

	rootiter = self.store.get_iter_first()
	sel = self.view.get_selection()
	sel.select_iter(rootiter)

        label = gtk.Label (_("It is recommended that your swap file be at "
                            "least %d MB.  Please enter a size for the swap "
                            "file:") % suggSize)
        label.set_size_request(400, 40)
        label.set_line_wrap (True)
        a = gtk.Alignment(0.5, 0.5)
        a.add(label)
        self.swapbox.pack_start(a, False, True, 10)


        hbox = gtk.HBox(False, 5)
        a = gtk.Alignment(0.4, 0.5)
        a.add(hbox)
        self.swapbox.pack_start(a, False)

        label = gui.MnemonicLabel (_("Swap file _size (MB):"))
        hbox.pack_start(label, False)

        self.entry = gtk.Entry(4)
        label.set_mnemonic_widget(self.entry)
        self.entry.set_size_request(40, 25)
        self.entry.set_text(str(suggSize))
        hbox.pack_start(self.entry, False, True, 10)

        self.option2 = gtk.RadioButton(self.option1,
                                      (_("I _don't want to create a swap "
                                         "file")))
        box.pack_start(self.option2, False, True, 20)

        self.option1.connect("toggled", self.toggle)
        return box


    def warning(self):
        rc = self.intf.messageWindow(_("Warning"), 
                    _("It is stongly recommended that you create a swap "
                      "file.  Failure to do so could cause the installer "
                      "to abort abnormally.  Are you sure that you wish "
                      "to continue?"), type = "yesno")
        return rc

    def swapWrongSize(self):
        rc = self.intf.messageWindow(_("Warning"), 
                    _("The swap file must be between 1 and 2000 MB in size."),
                       type = "okcancel")
        return rc

    def swapTooBig(self):
        
        rc = self.intf.messageWindow(_("Warning"), 
                    _("There is not enough space on the device you "
			  "selected for the swap partition."),
                       type = "okcancel")
        return rc
