#
# autopart_type.py: Allows the user to choose how they want to partition
#
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2005-2006 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#


import gtk
import gobject

import autopart
import rhpl
from rhpl.translate import _, N_
from constants import *
import gui
from partition_ui_helpers_gui import *
from netconfig_dialog import NetworkConfigurator

from iw_gui import *
from flags import flags
import network
import partitions
import partitioning

class PartitionTypeWindow(InstallWindow):
    def __init__(self, ics):
        InstallWindow.__init__(self, ics)
        ics.setTitle("Automatic Partitioning")
        ics.setNextEnabled(True)

    def getNext(self):
        if self.diskset.checkNoDisks():
            raise gui.StayOnScreen
        
        active = self.combo.get_active_iter()
        val = self.combo.get_model().get_value(active, 1)

        if val == -1:
            self.dispatch.skipStep("autopartitionexecute", skip = 1)
            self.dispatch.skipStep("partition", skip = 0)
            self.dispatch.skipStep("bootloader", skip = 0)
        else:
            self.dispatch.skipStep("autopartitionexecute", skip = 0)

            if self.xml.get_widget("encryptButton").get_active():
                self.partitions.autoEncrypt = True
            else:
                self.partitions.encryptionPassphrase = ""
                self.partitions.retrofitPassphrase = False
                self.partitions.autoEncrypt = False
            
            self.partitions.useAutopartitioning = 1
            self.partitions.autoClearPartType = val

            allowdrives = []
            model = self.drivelist.get_model()
            for row in model:
                if row[0]:
                    allowdrives.append(row[1])

            if len(allowdrives) < 1:
                mustHaveSelectedDrive(self.intf)
                raise gui.StayOnScreen

            self.partitions.autoClearPartDrives = allowdrives

            if not autopart.queryAutoPartitionOK(self.anaconda):
                raise gui.StayOnScreen

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
            self.xml.get_widget("encryptButton").set_sensitive(False)
        else:
            if self.prevrev == None:
               self.xml.get_widget("reviewButton").set_active(self.review)
            else:
               self.xml.get_widget("reviewButton").set_active(self.prevrev)
               self.prevrev = None

            self.xml.get_widget("reviewButton").set_sensitive(True)
            self.xml.get_widget("driveScroll").set_sensitive(True)
            self.xml.get_widget("encryptButton").set_sensitive(True)

    def addIscsiDrive(self):
        if not network.hasActiveNetDev():
            net = NetworkConfigurator(self.anaconda.id.network)
            ret = net.run()
            net.destroy()

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
        e.set_text(self.anaconda.id.iscsi.initiator)
        if self.anaconda.id.iscsi.initiatorSet: # this is uglyyyy....
            e.set_sensitive(False)

        while 1:
            rc = dialog.run()
            if rc == gtk.RESPONSE_CANCEL:
                break

            initiator = dxml.get_widget("iscsiInitiatorEntry").get_text()
            initiator.strip()
            if len(initiator) == 0:
                self.intf.messageWindow(_("Invalid Initiator Name"),
                                        _("You must provide a non-zero length "
                                          "initiator name."))
                continue

            self.anaconda.id.iscsi.initiator = initiator

            target = dxml.get_widget("iscsiAddrEntry").get_text().strip()
            user = dxml.get_widget("userEntry").get_text().strip()
            pw = dxml.get_widget("passEntry").get_text().strip()
            user_in = dxml.get_widget("userinEntry").get_text().strip()
            pw_in = dxml.get_widget("passinEntry").get_text().strip()

            err = None
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
            except network.IPMissing, msg:
                err = msg
            except network.IPError, msg:
                err = msg
            if err:
                self.intf.messageWindow(_("Error with Data"), "%s" %(err,))
                continue

            try:
                self.anaconda.id.iscsi.addTarget(ip, port, user, pw, user_in, pw_in,
                                                 self.intf)
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
                self.anaconda.id.zfcp.addFCP(devnum, wwpn, fcplun)
            except ValueError, e:
                self.intf.messageWindow(_("Error"), "%s" % e)
                continue
            break

        dialog.destroy()
        return rc
        

    def addDrive(self, button):
        (dxml, dialog) = gui.getGladeWidget("adddrive.glade", "addDriveDialog")
        gui.addFrame(dialog)
        dialog.show_all()
        if rhpl.getArch() not in ("s390", "s390x"):
            dxml.get_widget("zfcpRadio").hide()
            dxml.get_widget("zfcpRadio").set_group(None)

        import iscsi
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
        if dxml.get_widget("iscsiRadio").get_active():
            rc = self.addIscsiDrive()
        elif dxml.get_widget("zfcpRadio") is not None and dxml.get_widget("zfcpRadio").get_active():
            rc = self.addZfcpDrive()
        dialog.destroy()

        if rc != gtk.RESPONSE_CANCEL:
            w = self.intf.waitWindow(_("Rescanning disks"),
                                     _("Rescanning disks"))
            partitioning.partitionObjectsInitialize(self.anaconda)
            createAllowedDrivesStore(self.diskset.disks,
                                     self.partitions.autoClearPartDrives,
                                     self.drivelist,
                                     self.anaconda.updateSrc)
            w.pop()
        

    def getScreen(self, anaconda):
        self.anaconda = anaconda
        self.diskset = anaconda.id.diskset
        self.partitions = anaconda.id.partitions
        self.intf = anaconda.intf
        self.dispatch = anaconda.dispatch

        if anaconda.dir == DISPATCH_BACK:
            self.diskset.refreshDevices()
            self.partitions.setFromDisk(self.diskset)
            self.partitions.setProtected(anaconda.dispatch)

        (self.xml, vbox) = gui.getGladeWidget("autopart.glade", "parttypeBox")

        self.combo = self.xml.get_widget("partitionTypeCombo")
        cell = gtk.CellRendererText()
        self.combo.pack_start(cell, True)
        self.combo.set_attributes(cell, text = 0)
        cell.set_property("wrap-width", 455)
        self.combo.set_size_request(480, -1)

        store = gtk.TreeStore(gobject.TYPE_STRING, gobject.TYPE_INT)
        self.combo.set_model(store)
        opts = ((_("Remove all partitions on selected drives and create default layout."), CLEARPART_TYPE_ALL),
                (_("Remove linux partitions on selected drives and create default layout."), CLEARPART_TYPE_LINUX),
                (_("Use free space on selected drives and create default layout."), CLEARPART_TYPE_NONE),
                (_("Create custom layout."), -1))
        for (txt, val) in opts:
            iter = store.append(None)
            store[iter] = (txt, val)
            if val == self.partitions.autoClearPartType:
                self.combo.set_active_iter(iter)

        if ((self.combo.get_active() == -1) or
            self.dispatch.stepInSkipList("autopartitionexecute")):
            self.combo.set_active(len(opts) - 1) # yeah, it's a hack

        self.drivelist = createAllowedDrivesList(self.diskset.disks,
                                                 self.partitions.autoClearPartDrives,
                                                 self.anaconda.updateSrc)
        self.drivelist.set_size_request(375, 80)

        self.xml.get_widget("driveScroll").add(self.drivelist)

        self.prevrev = None
        self.review = not self.dispatch.stepInSkipList("partition")
        self.xml.get_widget("reviewButton").set_active(self.review)

        self.xml.get_widget("encryptButton").set_active(self.partitions.autoEncrypt)

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
            self.xml.get_widget("encryptButton").set_sensitive(False)

        sigs = { "on_partitionTypeCombo_changed": self.comboChanged,
                 "on_addButton_clicked": self.addDrive }
        self.xml.signal_autoconnect(sigs)

        return vbox
