#
# upgrade_swap_gui.py: dialog for adding swap files for 2.4
#
# Copyright (C) 2001, 2002  Red Hat, Inc.  All rights reserved.
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
# Author(s): Mike Fulbright <msf@redhat.com>
#

import iutil
import upgrade
import gui
import gobject
import gtk
from iw_gui import *
from flags import flags

from constants import *
import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

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
	    dev = model.get_value(iter, 0)
	    size = model.get_value(iter, 1)
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
            self.storage.createSwapFile(dev, val)
            self.dispatch.skipStep("addswap", 1)
                
        return None

    def toggle (self, data):
        self.swapbox.set_sensitive(self.option1.get_active())

    def clist_cb(self, clist, row, col, data):
        self.row = row
    
    def getScreen (self, anaconda):
        self.neededSwap = 0
        self.storage = anaconda.storage
        self.intf = anaconda.intf
        self.dispatch = anaconda.dispatch
        
        rc = anaconda.upgradeSwapInfo

        self.neededSwap = 1
        self.row = 0
        box = gtk.VBox (False, 5)
        box.set_border_width (5)

	label = gtk.Label (_("Recent kernels (2.4 or newer) need significantly more "
                            "swap than older kernels, up to twice "
                            "the amount of RAM on the system.  "
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

        for (dev, size) in fsList:
	    iter = self.store.append()
	    self.store.set_value(iter, 0, dev)
	    self.store.set_value(iter, 1, str(size))

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

        label = gtk.Label (_("A minimum swap file size of "
                            "%d MB is recommended.  Please enter a size for the swap "
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
                    _("A swap file is strongly recommended. "
                      "Failure to create one could cause the installer "
                      "to abort abnormally.  Are you sure you wish "
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
