#
# autopart_type.py: Allows the user to choose how they want to partition
#
# Copyright (C) 2005, 2006  Red Hat, Inc.  All rights reserved.
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
# Author(s): Jeremy Katz <katzj@redhat.com>
#

import gtk
import gobject
import math

from constants import *
import gui
from partition_ui_helpers_gui import *
from netconfig_dialog import NetworkConfigurator

from iw_gui import *
from flags import flags
import network
from storage import iscsi
from storage.deviceaction import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

def whichToResize(storage, intf):
    def getActive(combo):
        act = combo.get_active_iter()
        return combo.get_model().get_value(act, 1)

    def comboCB(combo, resizeSB):
        # partition to resize changed, let's update our spinbutton
        part = getActive(combo)
        reqlower = part.minSize
        requpper = part.maxSize

        adj = resizeSB.get_adjustment()
        adj.lower = reqlower
        adj.upper = requpper
        adj.value = reqlower
        adj.set_value(reqlower)


    (dxml, dialog) = gui.getGladeWidget("autopart.glade", "resizeDialog")

    store = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_PYOBJECT)
    combo = dxml.get_widget("resizePartCombo")
    combo.set_model(store)
    crt = gtk.CellRendererText()
    combo.pack_start(crt, True)
    combo.set_attributes(crt, text = 0)
    combo.connect("changed", comboCB, dxml.get_widget("resizeSB"))

    biggest = -1
    for part in storage.partitions:
        if not part.exists:
            continue

        # Resize the following storage types:
        #     resizable filesystem (e.g., ext3 or ntfs) on resizable partition
        #     resizable filesystem on a resizable logical volume
        entry = None
        if part.resizable and part.format.resizable:
            entry = ("%s (%s, %d MB)" % (part.name,
                                         part.format.name,
                                         math.floor(part.format.size)),
                     part)

        if entry:
            i = store.append(None)
            store[i] = entry
            combo.set_active_iter(i)

            if biggest == -1:
                biggest = i
            else:
                current = store.get_value(biggest, 1)
                if part.format.targetSize > current.format.targetSize:
                    biggest = i

    if biggest > -1:
        combo.set_active_iter(biggest)

    if len(store) == 0:
        dialog.destroy()
        intf.messageWindow(_("Error"),
                           _("No partitions are available to resize.  Only "
                             "physical partitions with specific filesystems "
                             "can be resized."),
                             type="warning", custom_icon="error")
        return (gtk.RESPONSE_CANCEL, [])

    gui.addFrame(dialog)
    dialog.show_all()
    runResize = True

    while runResize:
        rc = dialog.run()
        if rc != gtk.RESPONSE_OK:
            dialog.destroy()
            return (rc, [])

        request = getActive(combo)
        newSize = dxml.get_widget("resizeSB").get_value_as_int()
        actions = []

        try:
            actions.append(ActionResizeFormat(request, newSize))
        except ValueError as e:
            intf.messageWindow(_("Resize FileSystem Error"),
                               _("%s: %s") % (request.format.device,
                                              e.message,),
                               type="warning", custom_icon="error")
            continue

        try:
            actions.append(ActionResizeDevice(request, newSize))
        except ValueError as e:
            intf.messageWindow(_("Resize Device Error"),
                               _("%s: %s") % (request.name, e.message,),
                               type="warning", custom_icon="error")
            continue

        runResize = False

    dialog.destroy()
    return (rc, actions)

class PartitionTypeWindow(InstallWindow):
    def __init__(self, ics):
        InstallWindow.__init__(self, ics)
        ics.setTitle("Automatic Partitioning")
        ics.setNextEnabled(True)

    def getNext(self):
        if self.storage.checkNoDisks():
            raise gui.StayOnScreen
        
        active = self.combo.get_active_iter()
        val = self.combo.get_model().get_value(active, 1)

        if val == -1:
            self.dispatch.skipStep("autopartitionexecute", skip = 1)
            self.dispatch.skipStep("partition", skip = 0)
            self.dispatch.skipStep("bootloader", skip = 0)
        else:
            if val == -2:
                (rc, actions) = whichToResize(self.storage, self.intf)
                if rc == gtk.RESPONSE_OK:
                    for action in actions:
                        self.storage.devicetree.registerAction(action)
                else:
                    raise gui.StayOnScreen

                # we're not going to delete any partitions in the resize case
                val = CLEARPART_TYPE_NONE

            self.dispatch.skipStep("autopartitionexecute", skip = 0)

            if self.xml.get_widget("encryptButton").get_active():
                self.storage.encryptedAutoPart = True
            else:
                self.storage.encryptionPassphrase = ""
                self.storage.retrofitPassphrase = False
                self.storage.encryptedAutoPart = False
            
            self.storage.doAutoPart = True
            self.storage.clearPartType = val

            allowdrives = []
            model = self.drivelist.get_model()
            for row in model:
                if row[0]:
                    allowdrives.append(row[1])

            if len(allowdrives) < 1:
                mustHaveSelectedDrive(self.intf)
                raise gui.StayOnScreen

            self.storage.clearPartDisks = allowdrives

            # pop the boot device to be first in the drive list
            defiter = self.bootcombo.get_active_iter()
            if defiter is None:
                self.intf.messageWindow(_("Error"),
                                        "Must select a drive to use as "
                                        "the bootable device.",
                                        type="warning", custom_icon="error")
                raise gui.StayOnScreen
            
            defboot = self.bootcombo.get_model().get_value(defiter, 1)
           
            if not defboot in allowdrives:
                msg = _("Do you really want to boot from a disk which is not used for installation?")
                rc = self.intf.messageWindow(_("Warning"), msg, type="yesno", default="no", custom_icon ="warning")
                if not rc:
                    raise gui.StayOnScreen
            
            self.anaconda.id.bootloader.drivelist.remove(defboot)
            self.anaconda.id.bootloader.drivelist.insert(0, defboot)            

            if self.xml.get_widget("reviewButton").get_active():
                self.dispatch.skipStep("partition", skip = 0)
                self.dispatch.skipStep("bootloader", skip = 0)
            else:
                self.dispatch.skipStep("partition")
                self.dispatch.skipStep("bootloader")
                self.dispatch.skipStep("bootloaderadvanced")

        return None

    def comboChanged(self, *args):
        active = self.combo.get_active_iter()
        val = self.combo.get_model().get_value(active, 1)
        self.review = self.xml.get_widget("reviewButton").get_active()

        # -1 is the combo box choice for 'create custom layout'
        if val == -1:
            if self.prevrev == None:
               self.prevrev = self.xml.get_widget("reviewButton").get_active()

            self.xml.get_widget("reviewButton").set_active(True)
            self.xml.get_widget("reviewButton").set_sensitive(False)
            self.xml.get_widget("driveScroll").set_sensitive(False)
            self.xml.get_widget("bootDriveCombo").set_sensitive(False)
            self.xml.get_widget("encryptButton").set_sensitive(False)
        else:
            if self.prevrev == None:
               self.xml.get_widget("reviewButton").set_active(self.review)
            else:
               self.xml.get_widget("reviewButton").set_active(self.prevrev)
               self.prevrev = None

            self.xml.get_widget("reviewButton").set_sensitive(True)
            self.xml.get_widget("driveScroll").set_sensitive(True)
            self.xml.get_widget("bootDriveCombo").set_sensitive(True)
            self.xml.get_widget("encryptButton").set_sensitive(True)

    def addIscsiDrive(self):
        if not network.hasActiveNetDev():
            net = NetworkConfigurator(self.anaconda.id.network)
            ret = net.run()
            net.destroy()
            if ret != gtk.RESPONSE_OK:
                return ret

        (dxml, dialog) = gui.getGladeWidget("iscsi-config.glade",
                                            "iscsiDialog")
        gui.addFrame(dialog)
        dialog.show_all()
        sg = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
        map(lambda x: sg.add_widget(dxml.get_widget(x)),
            ("iscsiAddrEntry", "iscsiInitiatorEntry", "userEntry", "passEntry",
             "userinEntry", "passinEntry"))

        # get the initiator name if it exists and don't allow changing
        # once set
        e = dxml.get_widget("iscsiInitiatorEntry")
        e.set_text(self.storage.iscsi.initiator)
        if self.storage.iscsi.initiatorSet: # this is uglyyyy....
            e.set_sensitive(False)

        while 1:
            rc = dialog.run()
            if rc == gtk.RESPONSE_CANCEL:
                break

            initiator = dxml.get_widget("iscsiInitiatorEntry").get_text()
            initiator.strip()
            if len(initiator) == 0:
                self.intf.messageWindow(_("Invalid Initiator Name"),
                                        _("You must provide an initiator name."))
                continue

            self.storage.iscsi.initiator = initiator

            target = dxml.get_widget("iscsiAddrEntry").get_text().strip()
            user = dxml.get_widget("userEntry").get_text().strip()
            pw = dxml.get_widget("passEntry").get_text().strip()
            user_in = dxml.get_widget("userinEntry").get_text().strip()
            pw_in = dxml.get_widget("passinEntry").get_text().strip()

            if len(user) == 0:
                user = None
            if len(pw) == 0:
                pw = None
            if len(user_in) == 0:
                user_in = None
            if len(pw_in) == 0:
                pw_in = None

            err = None
            try:
                idx = target.rfind(":")
                if idx != -1:
                    ip = target[:idx]
                    port = target[idx:]
                else:
                    ip = target
                    port = "3260"
                network.sanityCheckIPString(ip)
            except network.IPMissing, msg:
                err = msg
            except network.IPError, msg:
                err = msg
            if err:
                self.intf.messageWindow(_("Error with Data"), "%s" %(err,))
                continue

            try:
                self.storage.iscsi.addTarget(ip, port, user, pw,
                                             user_in, pw_in, self.intf)
            except ValueError, e:
                self.intf.messageWindow(_("Error"), str(e))
                continue
            except IOError, e:
                self.intf.messageWindow(_("Error"), str(e))
                rc = gtk.RESPONSE_CANCEL
            break

        dialog.destroy()
        return rc


    def addZfcpDrive(self):
        (dxml, dialog) = gui.getGladeWidget("zfcp-config.glade",
                                            "zfcpDialog")
        gui.addFrame(dialog)
        dialog.show_all()
        sg = gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL)
        map(lambda x: sg.add_widget(dxml.get_widget(x)),
            ("devnumEntry", "wwpnEntry", "fcplunEntry"))

        while 1:
            rc = dialog.run()
            if rc != gtk.RESPONSE_APPLY:
                break

            devnum = dxml.get_widget("devnumEntry").get_text().strip()
            wwpn = dxml.get_widget("wwpnEntry").get_text().strip()
            fcplun = dxml.get_widget("fcplunEntry").get_text().strip()

            try:
                self.storage.zfcp.addFCP(devnum, wwpn, fcplun)
            except ValueError, e:
                self.intf.messageWindow(_("Error"), str(e))
                continue
            break

        dialog.destroy()
        return rc
        

    def addDrive(self, button):
        (dxml, dialog) = gui.getGladeWidget("adddrive.glade", "addDriveDialog")
        gui.addFrame(dialog)
        dialog.show_all()
        if not iutil.isS390():
            dxml.get_widget("zfcpRadio").hide()
            dxml.get_widget("zfcpRadio").set_group(None)

        if not iscsi.has_iscsi():
            dxml.get_widget("iscsiRadio").set_sensitive(False)
            dxml.get_widget("iscsiRadio").set_active(False)

        #figure out what advanced devices we have available and set sensible default
        group = dxml.get_widget("iscsiRadio").get_group()
        for button in group:
            if button is not None and button.get_property("sensitive"):
                button.set_active(True)
                break
        
        rc = dialog.run()
        dialog.hide()
        if rc == gtk.RESPONSE_CANCEL:
            return
        if dxml.get_widget("iscsiRadio").get_active() and iscsi.has_iscsi():
            rc = self.addIscsiDrive()
        elif dxml.get_widget("zfcpRadio") is not None and dxml.get_widget("zfcpRadio").get_active():
            rc = self.addZfcpDrive()
        dialog.destroy()

        if rc != gtk.RESPONSE_CANCEL:
            w = self.intf.waitWindow(_("Rescanning disks"),
                                     _("Rescanning disks"))
            self.storage.reset()
            createAllowedDrivesStore(self.storage.disks,
                                     self.storage.clearPartDisks,
                                     self.drivelist,
                                     disallowDrives=[self.anaconda.updateSrc])
            self._fillBootStore()
            w.pop()

    def _fillBootStore(self):
        bootstore = self.bootcombo.get_model()
        bootstore.clear()
        if len(self.anaconda.id.bootloader.drivelist) > 0:
            defaultBoot = self.anaconda.id.bootloader.drivelist[0]
        else:
            defaultBoot = None
        for disk in self.storage.disks:
            if disk.name not in self.anaconda.id.bootloader.drivelist:
                continue
            dispstr = "%s %8.0f MB %s" %(disk.name, disk.size, disk.partedDisk.device.model)
            i = bootstore.append(None)
            bootstore[i] = (dispstr, disk.name)
            if disk.name == defaultBoot:
                self.bootcombo.set_active_iter(i)

        if len(bootstore) <= 1:
            self.bootcombo.set_sensitive(False)


    def getScreen(self, anaconda):
        self.anaconda = anaconda
        self.storage = anaconda.id.storage
        self.intf = anaconda.intf
        self.dispatch = anaconda.dispatch

        (self.xml, vbox) = gui.getGladeWidget("autopart.glade", "parttypeBox")

        # make some labels bold...
        map(lambda l: l and l.set_markup("<b>%s</b>" %(l.get_text(),)),
            map(lambda x: self.xml.get_widget(x),("selectLabel", "bootLabel")))

        gui.widgetExpander(self.xml.get_widget("mainlabel"))

        self.combo = self.xml.get_widget("partitionTypeCombo")
        gui.widgetExpander(self.combo)
        cell = gtk.CellRendererText()
        self.combo.pack_start(cell, True)
        self.combo.set_attributes(cell, text = 0)
        cell.set_property("wrap-width", 495)
        self.combo.set_size_request(500, -1)

        store = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_INT)
        self.combo.set_model(store)
        opts = ((_("Use entire drive"), CLEARPART_TYPE_ALL),
                (_("Replace existing Linux system"), CLEARPART_TYPE_LINUX),
                (_("Shrink current system"), -2),
                (_("Use free space"), CLEARPART_TYPE_NONE),
                (_("Create custom layout"), -1))
        for (txt, val) in opts:
            iter = store.append(None)
            store[iter] = (txt, val)
            if val == self.storage.clearPartType:
                self.combo.set_active_iter(iter)

        if ((self.combo.get_active() == -1) or
            self.dispatch.stepInSkipList("autopartitionexecute")):
            self.combo.set_active(len(opts) - 1) # yeah, it's a hack

        self.drivelist = createAllowedDrivesList(self.storage.disks,
                                                 self.storage.clearPartDisks,
                                                 disallowDrives=[self.anaconda.updateSrc])
        self.drivelist.set_size_request(375, 80)

        self.xml.get_widget("driveScroll").add(self.drivelist)

        self.bootcombo = self.xml.get_widget("bootDriveCombo")
        thecell = gtk.CellRendererText()
        self.bootcombo.pack_start(thecell, True)

        bootstore = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
        self.bootcombo.set_model(bootstore)
        self._fillBootStore()

        self.prevrev = None
        self.review = not self.dispatch.stepInSkipList("partition")
        self.xml.get_widget("reviewButton").set_active(self.review)

        self.xml.get_widget("encryptButton").set_active(self.storage.encryptedAutoPart)

        active = self.combo.get_active_iter()
        val = self.combo.get_model().get_value(active, 1)

        # -1 is the combo box choice for 'create custom layout'
        if val == -1:
            # make sure reviewButton is active and not sensitive
            if self.prevrev == None:
               self.prevrev = self.xml.get_widget("reviewButton").get_active()

            self.xml.get_widget("reviewButton").set_active(True)
            self.xml.get_widget("reviewButton").set_sensitive(False)

            self.xml.get_widget("driveScroll").set_sensitive(False)
            self.xml.get_widget("bootDriveCombo").set_sensitive(False)
            self.xml.get_widget("encryptButton").set_sensitive(False)

        if not iutil.isS390() and not iscsi.has_iscsi():
            self.xml.get_widget("addButton").set_sensitive(False)

        sigs = { "on_partitionTypeCombo_changed": self.comboChanged,
                 "on_addButton_clicked": self.addDrive }
        self.xml.signal_autoconnect(sigs)

        return vbox
