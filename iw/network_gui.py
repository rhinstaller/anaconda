#
# network_gui.py: Network configuration dialog
#
# Michael Fulbright <msf@redhat.com>
#
# Copyright 2000-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import string
import gtk
import gobject
from iw_gui import *
import isys
import gui
from rhpl.translate import _, N_
import network
import checklist

global_options = [_("Gateway"), _("Primary DNS"),
		  _("Secondary DNS"), _("Tertiary DNS")]

global_option_labels = [_("_Gateway"), _("_Primary DNS"),
		  _("_Secondary DNS"), _("_Tertiary DNS")]

class NetworkWindow(InstallWindow):		

    windowTitle = N_("Network Configuration")

    def __init__(self, ics):
	InstallWindow.__init__(self, ics)

    def getNext(self):

	if self.getNumberActiveDevices() == 0:
	    rc = self.handleNoActiveDevices()
	    if not rc:
		raise gui.StayOnScreen

	override = 0
	if self.hostnameManual.get_active():
	    hname = string.strip(self.hostnameEntry.get_text())
	    neterrors =  network.sanityCheckHostname(hname)
	    if neterrors is not None:
		self.handleBadHostname(hname, neterrors) 
		raise gui.StayOnScreen
            elif len(hname) == 0:
                hname = "localhost.localdomain" # ...better than empty
		if ((self.getNumberActiveDevices() > 0) and
                    self.handleMissingHostname()):
		    raise gui.StayOnScreen

	    newHostname = hname
            override = 1
	else:
	    newHostname = "localhost.localdomain"
	    override = 0

	# If we're not using DHCP, skip setting up the network config
	# boxes.  Otherwise, don't clear the values out if we are doing
	# kickstart since we could be in interactive mode.  Don't want to
	# write out a broken resolv.conf later on, after all.
	if not self.anyUsingDHCP():
	    tmpvals = {}
	    for t in range(len(global_options)):
		try:
                    network.sanityCheckIPString(self.globals[global_options[t]])
		    tmpvals[t] = self.globals[global_options[t]]
		except network.IPMissing, msg:
                    if t < 2 and self.getNumberActiveDevices() > 0:
			if self.handleMissingOptionalIP(global_options[t]):
			    raise gui.StayOnScreen
			else:
			    tmpvals[t] = None
		    else:
			    tmpvals[t] = None
			
		except network.IPError, msg:
		    self.handleIPError(global_options[t], msg)
		    raise gui.StayOnScreen

	    self.network.gateway = tmpvals[0]
	    self.network.primaryNS = tmpvals[1]
	    self.network.secondaryNS = tmpvals[2]
	    self.network.ternaryNS = tmpvals[3]
	elif self.id.instClass.name != "kickstart":
	    self.network.gateway = None
	    self.network.primaryNS = None
	    self.network.secondaryNS = None
	    self.network.ternaryNS = None

        iter = self.ethdevices.store.get_iter_first()
	while iter:
	    model = self.ethdevices.store
	    dev = model.get_value(iter, 1)
	    bootproto = model.get_value(iter, 2)
	    onboot = model.get_value(iter, 0)

	    if onboot:
		onboot = "yes"
	    else:
		onboot = "no"
		
	    if bootproto == "DHCP":
		bootproto = 'dhcp'
	    else:
		bootproto = 'static'
		
	    self.devices[dev].set(("ONBOOT", onboot))
	    self.devices[dev].set(("bootproto", bootproto))
            iter = self.ethdevices.store.iter_next(iter)

	self.network.hostname = newHostname
	self.network.overrideDHCPhostname = override

        return None
        
    def DHCPtoggled(self, widget, (dev, table)):
	active = widget.get_active()
        table.set_sensitive(not active)
	
	bootproto = "dhcp"
	if not active:
            bootproto = "static"

    def onBootToggled(self, widget, dev):
	if widget.get_active():
	    onboot = "yes"
	else:
	    onboot = "no"
	dev.set(("ONBOOT", onboot))

    def setHostOptionsSensitivity(self):
        # figure out if they have overridden using dhcp for hostname
	if self.anyUsingDHCP():
	    self.hostnameUseDHCP.set_sensitive(1)

	    if self.hostname != "localhost.localdomain" and self.network.overrideDHCPhostname:
		self.hostnameManual.set_active(1)
		self.hostnameManual.set_sensitive(1)
	    else:
		self.hostnameUseDHCP.set_active(1)
	else:
	    self.hostnameManual.set_active(1)
	    self.hostnameUseDHCP.set_sensitive(0)

    def setIPTableSensitivity(self):
	numactive = self.getNumberActiveDevices()
	if numactive == 0:
	    state = False
	else:
	    state = not self.anyUsingDHCP()

	self.ipTable.set_sensitive(state)

    def handleMissingHostname(self):
	return not self.intf.messageWindow(_("Error With Data"),
				_("You have not specified a hostname.  Depending on your network environment this may cause problems later."), type="custom", custom_buttons=["gtk-cancel", _("C_ontinue")])

    def handleMissingOptionalIP(self, field):
	return not self.intf.messageWindow(_("Error With Data"),
				_("You have not specified the field \"%s\".  Depending on your network environment this may cause problems later.") % (field,), type="custom", custom_buttons=["gtk-cancel", _("C_ontinue")])

    def handleBadHostname(self, hostname, error):
	self.intf.messageWindow(_("Error With Data"),
				_("The hostname \"%s\" is not valid for the following reason:\n\n%s") % (hostname, error))

    def handleIPError(self, field, errmsg):
	newfield = string.replace(field, "_", "")
	self.intf.messageWindow(_("Error With Data"),
				_("An error occurred converting "
				  "the value entered for \"%s\":\n%s") % (newfield, errmsg))

    def handleIPMissing(self, field):
	newfield = string.replace(field, "_", "")
	self.intf.messageWindow(_("Error With Data"),
				_("A value is required for the field \"%s\".") % (newfield,))

    def handleBroadCastError(self):
	self.intf.messageWindow(_("Error With Data"),
				_("The IP information you have entered is "
				  "invalid."))

    def handleNoActiveDevices(self):
	return self.intf.messageWindow(_("Error With Data"), _("You have no active network devices.  Your system will not be able to communicate over a network by default without at least one device active."), type="custom", custom_buttons=["gtk-cancel", _("C_ontinue")])
    
    def editDevice(self, data):
	if self.ignoreEvents:
	    return
	
	selection = self.ethdevices.get_selection()
        (model, iter) = selection.get_selected()
        if not iter:
            return None

        dev = model.get_value(iter, 1)
	bootproto = model.get_value(iter, 2)
	onboot = model.get_value(iter, 0)

	# create dialog box
        editWin = gtk.Dialog(_("Edit Interface %s") % (dev,),
			     flags=gtk.DIALOG_MODAL)
        gui.addFrame(editWin)
        editWin.set_modal(True)
#        editWin.set_size_request(350, 200)
        editWin.set_position (gtk.WIN_POS_CENTER)
	
	# create contents
	devbox = gtk.VBox()

	align = gtk.Alignment()
	DHCPcb = gtk.CheckButton(_("Configure using _DHCP"))

	align.add(DHCPcb)
	devbox.pack_start(align, False)

	align = gtk.Alignment()
	bootcb = gtk.CheckButton(_("_Activate on boot"))

	bootcb.connect("toggled", self.onBootToggled, self.devices[dev])
	bootcb.set_active(onboot)
	align.add(bootcb)

	devbox.pack_start(align, False, padding=6)
#	devbox.pack_start(gtk.HSeparator(), False, padding=3)

	options = [(_("_IP Address"), "ipaddr"),
		   (_("Net_mask"),    "netmask")]

        devopts = []

        if (network.isPtpDev(dev)):
	    newopt = (_("_Point to Point (IP)"), "remip")
	    options.append(newopt)

        if (isys.isWireless(dev)):
            newopt = [(_("_ESSID"), "essid"),
                      (_("Encryption _Key"), "key")]
            devopts.extend(newopt)
            
        ipTable = gtk.Table(len(options) + 1, 2)
	DHCPcb.connect("toggled", self.DHCPtoggled, (self.devices[dev], ipTable))
	# go ahead and set up DHCP on the first device
	DHCPcb.set_active(bootproto == 'DHCP')
	entrys = {}

        hwaddr = self.devices[dev].get("hwaddr")
        if hwaddr is not None and len(hwaddr) > 0:
            label = gui.MnemonicLabel(_("Hardware address:"), (0.0, 0.5))
            ipTable.attach(label, 0, 1, 0, 1, gtk.FILL, 0, 10, 5)
            hwlabel = gtk.Label("%s" %(hwaddr,))
            ipTable.attach(hwlabel, 1, 2, 0, 1)
        
	for t in range(len(options)):
	    label = gtk.Label("%s:" %(options[t][0],))
	    label.set_alignment(0.0, 0.5)
	    label.set_property("use-underline", True)
	    ipTable.attach(label, 0, 1, t+1, t+2, gtk.FILL, 0, 10)

            entry = gtk.Entry()
	    entrys[t] = entry
	    label.set_mnemonic_widget(entry)
	    ipTable.attach(entry, 1, 2, t+1, t+2, 0, gtk.FILL|gtk.EXPAND)

	devbox.pack_start(ipTable, False, False, 6)
        devbox.set_border_width(6)

        deventrys = {}
        if len(devopts) > 0:
            devTable = gtk.Table(len(devopts), 2)

            for t in range(len(devopts)):
                label = gtk.Label("%s:" %(devopts[t][0],))
                label.set_alignment(0.0, 0.5)
                label.set_property("use-underline", True)
                devTable.attach(label, 0, 1, t, t+1, gtk.FILL, 0, 10)

                entry = gtk.Entry()
                entry.set_text(self.devices[dev].get(devopts[t][1]))
                deventrys[t] = entry
                label.set_mnemonic_widget(entry)
                devTable.attach(entry, 1, 2, t, t+1, 0, gtk.FILL|gtk.EXPAND)


            devbox.pack_start(devTable, False, False, 6)

	framelab = _("Configure %s") % (dev,)
	descr = self.devices[dev].get("desc")
	if descr is not None and len(descr) > 0:
	    framelab += " - " + descr[:70]
        
        l = gtk.Label()
        l.set_markup("<b>%s</b>" %(framelab,))
	
	frame = gtk.Frame()
        frame.set_label_widget(l)
	frame.set_border_width(12)
	frame.add(devbox)
        frame.set_shadow_type(gtk.SHADOW_NONE)
	editWin.vbox.pack_start(frame, padding=6)
        editWin.set_position(gtk.WIN_POS_CENTER)
	editWin.show_all()
        editWin.add_button('gtk-cancel', 2)
	editWin.add_button('gtk-ok', 1)

	while 1:
	    rc = editWin.run()

	    if rc == 2:
                editWin.destroy()
                return

	    if DHCPcb.get_active():
		bootproto = 'dhcp'
	    else:
		bootproto = 'static'


	    if bootcb.get_active():
		onboot = 'yes'
	    else:
		onboot = 'no'

	    if bootproto != 'dhcp':
		valsgood = 1
		tmpvals = {}
		for t in range(len(options)):
		    try:
                        network.sanityCheckIPString(entrys[t].get_text())
                        tmpvals[t] = entrys[t].get_text()
		    except network.IPMissing, msg:
			self.handleIPMissing(options[t][0])
			valsgood = 0
			break
		    except network.IPError, msg:
			self.handleIPError(options[t][0], msg)
			valsgood = 0
			break

		if valsgood == 0:
		    continue

		try:
                    (net, bc) = isys.inet_calcNetBroad (tmpvals[0], tmpvals[1])
		except Exception, e:
                    print e
		    self.handleBroadCastError()
		    valsgood = 0

		if not valsgood:
		    continue

		for t in range(len(options)):
		    self.devices[dev].set((options[t][1], tmpvals[t]))

		self.devices[dev].set(('network', net), ('broadcast', bc))

	    self.devices[dev].set(('bootproto', bootproto))
	    self.devices[dev].set(('ONBOOT', onboot))
	    model.set_value(iter, 0, onboot == 'yes')
	    model.set_value(iter, 2, self.createIPRepr(self.devices[dev]))

            for t in range(len(devopts)):
                self.devices[dev].set((devopts[t][1], deventrys[t].get_text()))

	    editWin.destroy()

	    self.setIPTableSensitivity()
	    self.setHostOptionsSensitivity()

	    return

    def createIPRepr(self, device):
	bootproto = device.get("bootproto")
	if bootproto == "dhcp":
	    ip = "DHCP"
	else:
	    ip = "%s/%s" % (device.get("ipaddr"), device.get("netmask"))

	return ip

    def getNumberActiveDevices(self):
        iter = self.ethdevices.store.get_iter_first()
	numactive = 0
	while iter:
	    model = self.ethdevices.store
	    if model.get_value(iter, 0):
		numactive = numactive + 1
		break
            iter = self.ethdevices.store.iter_next(iter)

	return numactive

    def anyUsingDHCP(self):
	for device in self.devices.keys():
	    bootproto = self.devices[device].get("bootproto")

	    if bootproto and bootproto == 'dhcp':
		onboot = self.devices[device].get("ONBOOT")
		if onboot != "no":
		    return 1

	return 0
	
    def onbootToggleCB(self, row, data):
	model = self.ethdevices.get_model()
	iter = model.get_iter((string.atoi(data),))
	val = model.get_value(iter, 0)
	dev = model.get_value(iter, 1)
	if val:
	    onboot = "yes"
	else:
	    onboot = "no"
	    
	self.devices[dev].set(("ONBOOT", onboot))
	
	self.setIPTableSensitivity()
	self.setHostOptionsSensitivity()
	
	return
    
	
    def setupDevices(self):
	devnames = self.devices.keys()
	devnames.sort()

	store = gtk.TreeStore(gobject.TYPE_BOOLEAN,
			  gobject.TYPE_STRING,
			  gobject.TYPE_STRING)
	
	self.ethdevices = NetworkDeviceCheckList(2, store, clickCB=self.onbootToggleCB)
        num = 0
        for device in devnames:
	    onboot = self.devices[device].get("ONBOOT")
	    if ((num == 0 and not onboot) or onboot == "yes"):
		active = True
	    else:
		active = False

	    bootproto = self.devices[device].get("bootproto")
	    if not bootproto:
		bootproto = 'dhcp'
		self.devices[device].set(("bootproto", bootproto))
		
	    ip = self.createIPRepr(self.devices[device])

# only if we want descriptions in the master device list
# currently too wide, but might be able to do it with a tooltip on
# each row once I figure out how (can't be done: b.g.o #80980)
# would require adding extra text field to end of store above as well
#
#	    descr = self.devices[device].get("desc")
#	    if descr is None:
#		descr = ""
#		
#	    self.ethdevices.append_row((device, ip, descr), active)
#
# use this for now
            self.ethdevices.append_row((device, ip), active)

            num += 1

	self.ethdevices.set_column_title(0, (_("Active on Boot")))
        self.ethdevices.set_column_sizing (0, gtk.TREE_VIEW_COLUMN_GROW_ONLY)
	self.ethdevices.set_column_title(1, (_("Device")))
        self.ethdevices.set_column_sizing (1, gtk.TREE_VIEW_COLUMN_GROW_ONLY)
	self.ethdevices.set_column_title(2, (_("IP/Netmask")))
        self.ethdevices.set_column_sizing (2, gtk.TREE_VIEW_COLUMN_GROW_ONLY)
#	self.ethdevices.set_column_title(3, (_("Description")))
#        self.ethdevices.set_column_sizing (3, gtk.TREE_VIEW_COLUMN_GROW_ONLY)
        self.ethdevices.set_headers_visible(True)

	self.ignoreEvents = 1
	iter = self.ethdevices.store.get_iter_first()
	selection = self.ethdevices.get_selection()
	selection.set_mode(gtk.SELECTION_BROWSE)
	selection.select_iter(iter)
	self.ignoreEvents = 0

	return self.ethdevices

    def hostnameUseDHCPCB(self, widget, data):
	self.network.overrideDHCPhostname = 0
	self.hostnameEntry.set_sensitive(not widget.get_active())

    def hostnameManualCB(self, widget, data):
	self.network.overrideDHCPhostname = 1
	if widget.get_active():
	    self.hostnameEntry.grab_focus()

    # NetworkWindow tag="netconf"
    def getScreen(self, anaconda):
	self.intf = anaconda.intf
	self.id = anaconda.id
        box = gtk.VBox(False)
        box.set_spacing(6)
	self.network = anaconda.id.network
        
        self.devices = self.network.available()
	
        if not self.devices:
	    return None

	self.numdevices = len(self.devices.keys())

	self.hostname = self.network.hostname

	devhbox = gtk.HBox(False)
	devhbox.set_spacing(12)

	self.devlist = self.setupDevices()

	devlistSW = gtk.ScrolledWindow()
        devlistSW.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        devlistSW.set_shadow_type(gtk.SHADOW_IN)
        devlistSW.add(self.devlist)
	devlistSW.set_size_request(-1, 100)
	devhbox.pack_start(devlistSW, False)

        buttonbar = gtk.VButtonBox()
        buttonbar.set_layout(gtk.BUTTONBOX_START)
	edit = gtk.Button(_("_Edit"))
        edit.connect("clicked", self.editDevice)
	buttonbar.pack_start(edit, False)
	devhbox.pack_start(buttonbar, False)
        devhbox.set_border_width(6)

        l = gtk.Label()
        l.set_markup("<b>%s</b>" %(_("Network Devices"),))
	frame=gtk.Frame()
        frame.set_label_widget(l)
	frame.add(devhbox)
        frame.set_shadow_type(gtk.SHADOW_NONE)
	box.pack_start(frame, False)
	
	# show hostname and dns/misc network info and offer chance to modify
	hostbox=gtk.VBox()
	hostbox.set_spacing(6)

	label=gtk.Label(_("Set the hostname:"))
	label.set_alignment(0.0, 0.0)
	hostbox.pack_start(label, False, False)

	tmphbox=gtk.HBox()
        self.hostnameUseDHCP = gtk.RadioButton(label=_("_automatically via DHCP"))
	self.hostnameUseDHCP.connect("toggled", self.hostnameUseDHCPCB, None)
	tmphbox.pack_start (self.hostnameUseDHCP, False, False)
	hostbox.pack_start(tmphbox, False, False)

	tmphbox=gtk.HBox()
	tmphbox.set_spacing(6)
	self.hostnameManual = gtk.RadioButton(group=self.hostnameUseDHCP, label=_("_manually"))
	tmphbox.pack_start(self.hostnameManual, False, False)
	self.hostnameEntry = gtk.Entry()
	tmphbox.pack_start(self.hostnameEntry, False, False)
	tmphbox.pack_start(gtk.Label(_('(ex. "host.domain.com")')), False, False)
	self.hostnameManual.connect("toggled", self.hostnameManualCB, None)
	hostbox.pack_start(tmphbox, False, False)

	hostbox.set_border_width(6)
        l = gtk.Label()
        l.set_markup("<b>%s</b>" %(_("Hostname"),))
	frame=gtk.Frame()
        frame.set_label_widget(l)
	frame.add(hostbox)
        frame.set_shadow_type(gtk.SHADOW_NONE)
	box.pack_start(frame, False, False)


        self.setHostOptionsSensitivity()
        
        #
	# this is the iptable used for DNS, et. al
	self.ipTable = gtk.Table(len(global_options), 2)
#	self.ipTable.set_row_spacing(0, 5)
	options = {}
	for i in range(len(global_options)):
	    label = gtk.Label("%s:" %(global_option_labels[i],))
	    label.set_property("use-underline", True)
	    label.set_alignment(0.0, 0.0)
	    self.ipTable.attach(label, 0, 1, i, i+1, gtk.FILL, 0)
	    align = gtk.Alignment(0, 0.5)
	    options[i] = gtk.Entry()
	    align.add(options[i])
	    label.set_mnemonic_widget(options[i])

	    self.ipTable.attach(align, 1, 2, i, i+1, gtk.FILL, 0)


	self.globals = {}
	for t in range(len(global_options)):
	    self.globals[global_options[t]] = options[t].get_text()

	# bring over the value from the loader
	self.hostnameEntry.set_text(self.network.hostname)

	if not self.anyUsingDHCP():
	    if self.network.gateway:
                self.globals[_("Gateway")] = self.network.gateway
                options[0].set_text(self.network.gateway)
	    if self.network.primaryNS:
                self.globals[_("Primary DNS")] = self.network.primaryNS
                options[1].set_text(self.network.primaryNS)
	    if self.network.secondaryNS:
                self.globals[_("Secondary DNS")] = self.network.secondaryNS
                options[2].set_text(self.network.secondaryNS)
	    if self.network.ternaryNS:
                self.globals[_("Tertiary DNS")] = self.network.ternaryNS
                options[3].set_text(self.network.ternaryNS)

	self.ipTable.set_border_width(6)

        l = gtk.Label()
        l.set_markup("<b>%s</b>" %(_("Miscellaneous Settings"),))
	frame=gtk.Frame()
        frame.set_label_widget(l)
	frame.add(self.ipTable)
        frame.set_shadow_type(gtk.SHADOW_NONE)
	box.pack_start(frame, False, False)
	box.set_border_width(6)

	self.hostnameEntry.set_sensitive(not self.hostnameUseDHCP.get_active())
	self.setIPTableSensitivity()

        self.hostnameUseDHCP.set_sensitive(self.anyUsingDHCP())

	return box


class NetworkDeviceCheckList(checklist.CheckList):
    def toggled_item(self, data, row):
	checklist.CheckList.toggled_item(self, data, row)

	if self.clickCB:
	    rc = self.clickCB(data, row)
    
    def __init__(self, columns, store, clickCB=None):
	checklist.CheckList.__init__(self, columns=columns,
				     custom_store=store)

	self.clickCB = clickCB
