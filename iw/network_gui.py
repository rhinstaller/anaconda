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
from iw_gui import *
from isys import *
import gui
from rhpl.translate import _, N_
import network
import checklist
import ipwidget
import iutil

global_options = [_("Gateway"), _("Primary DNS"),
		  _("Secondary DNS"), _("Tertiary DNS")]

global_option_labels = [_("_Gateway"), _("_Primary DNS"),
		  _("_Secondary DNS"), _("_Tertiary DNS")]

class NetworkWindow(InstallWindow):		

    windowTitle = N_("Network Configuration")
    if iutil.getArch() == "s390":
        htmlTag = "netconf-s390"
    else:
        htmlTag = "netconf"

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
		if self.handleMissingHostname():
		    raise gui.StayOnScreen

	    newHostname = hname
	    override = self.anyUsingDHCP()
	else:
	    newHostname = "localhost.localdomain"
	    override = 0

	if not self.anyUsingDHCP():
	    tmpvals = {}
	    for t in range(len(global_options)):
		try:
		    tmpvals[t] = self.globals[global_options[t]].dehydrate()
		except ipwidget.IPMissing, msg:
		    if t < 2:
			if self.handleMissingOptionalIP(global_options[t]):
			    raise gui.StayOnScreen
			else:
			    tmpvals[t] = None
		    else:
			    tmpvals[t] = None
			
		except ipwidget.IPError, msg:
		    self.handleIPError(global_options[t], msg[0])
		    raise gui.StayOnScreen

	    self.network.gateway = tmpvals[0]
	    self.network.primaryNS = tmpvals[1]
	    self.network.secondaryNS = tmpvals[2]
	    self.network.ternaryNS = tmpvals[3]
	else:
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
	if not self.anyUsingDHCP():
	    self.hostnameManual.set_active(1)
	else:
	    self.hostnameUseDHCP.set_active(1)
	    
        self.hostnameUseDHCP.set_sensitive(self.anyUsingDHCP())


    def setIPTableSensitivity(self):
	numactive = self.getNumberActiveDevices()
	if numactive == 0:
	    state = gtk.FALSE
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
				  "the value entered for \"%s\":\n%s" % (newfield, errmsg)))

    def handleIPMissing(self, field):
	newfield = string.replace(field, "_", "")
	self.intf.messageWindow(_("Error With Data"),
				_("A value is required for the field \"%s\"." % (newfield,)))

    def handleBroadCastError(self):
	self.intf.messageWindow(_("Error With Data"),
				_("The IP information you have entered is "
				  "invalid."))

    def handleNoActiveDevices(self):
	return self.intf.messageWindow(_("Error With Data"), _("You have no active network devices.  Your system will not be able to communicate over a network by default without at least one device active.\n\nNOTE: If you have a PCMCIA-based network adapter you should leave it inactive at this point. When you reboot your system the adapter will be activated automatically."), type="custom", custom_buttons=["gtk-cancel", _("C_ontinue")])
    
    def setHostnameRadioState(self):
	pass

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
        editWin.set_modal(gtk.TRUE)
#        editWin.set_size_request(350, 200)
        editWin.set_position (gtk.WIN_POS_CENTER)
	
	# create contents
	devbox = gtk.VBox()
	align = gtk.Alignment()
	DHCPcb = gtk.CheckButton(_("Configure using _DHCP"))

	align.add(DHCPcb)
	devbox.pack_start(align, gtk.FALSE)

	align = gtk.Alignment()
	bootcb = gtk.CheckButton(_("_Activate on boot"))

	bootcb.connect("toggled", self.onBootToggled, self.devices[dev])
	bootcb.set_active(onboot)
	align.add(bootcb)

	devbox.pack_start(align, gtk.FALSE)
	devbox.pack_start(gtk.HSeparator(), gtk.FALSE, padding=3)

	options = [(_("_IP Address"), "ipaddr"),
		   (_("Net_mask"),    "netmask")]

	if len(dev) >= 3 and dev[:3] == 'ctc':
	    newopt = (_("Point to Point (IP)"), "remip")
	    options.append(newopt)
            
        ipTable = gtk.Table(len(options), 2)
        iptable = None
	DHCPcb.connect("toggled", self.DHCPtoggled, (self.devices[dev], ipTable))
	# go ahead and set up DHCP on the first device
	DHCPcb.set_active(bootproto == 'DHCP')
	entrys = {}
	for t in range(len(options)):
	    label = gtk.Label("%s:" %(options[t][0],))
	    label.set_alignment(0.0, 0.5)
	    label.set_property("use-underline", gtk.TRUE)
	    ipTable.attach(label, 0, 1, t, t+1, gtk.FILL, 0, 10)

	    entry = ipwidget.IPEditor()
	    entry.hydrate(self.devices[dev].get(options[t][1]))
	    entrys[t] = entry
	    label.set_mnemonic_widget(entry.getFocusableWidget())
	    ipTable.attach(entry.getWidget(), 1, 2, t, t+1, 0, gtk.FILL|gtk.EXPAND)

	devbox.pack_start(ipTable, gtk.FALSE, gtk.FALSE, 5)

	frame = gtk.Frame(_("Configure %s" % (dev,)))
	frame.add(devbox)
	editWin.vbox.pack_start(frame, padding=5)
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
			tmpvals[t] = entrys[t].dehydrate()
		    except ipwidget.IPMissing, msg:
			self.handleIPMissing(options[t][0])
			valsgood = 0
			break
		    except ipwidget.IPError, msg:
			self.handleIPError(options[t][0], msg[0])
			valsgood = 0
			break

		if valsgood == 0:
		    continue

		try:
                    (net, bc) = inet_calcNetBroad (tmpvals[0], tmpvals[1])
		except:
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

	self.ethdevices = NetworkDeviceCheckList(2, clickCB=self.onbootToggleCB)

        num = 0
        for device in devnames:
	    onboot = self.devices[device].get("ONBOOT")
	    if ((num == 0 and not onboot) or onboot == "yes"):
		active = gtk.TRUE
	    else:
		active = gtk.FALSE

	    bootproto = self.devices[device].get("bootproto")
	    if not bootproto:
		bootproto = 'dhcp'
		self.devices[device].set(("bootproto", bootproto))
		
	    ip = self.createIPRepr(self.devices[device])

	    self.ethdevices.append_row((device, ip), active)

	self.ethdevices.set_column_title(0, (_("Active on Boot")))
        self.ethdevices.set_column_sizing (0, gtk.TREE_VIEW_COLUMN_GROW_ONLY)
	self.ethdevices.set_column_title(1, (_("Device")))
        self.ethdevices.set_column_sizing (1, gtk.TREE_VIEW_COLUMN_GROW_ONLY)
	self.ethdevices.set_column_title(2, (_("IP/Netmask")))
        self.ethdevices.set_column_sizing (2, gtk.TREE_VIEW_COLUMN_GROW_ONLY)
        self.ethdevices.set_headers_visible(gtk.TRUE)

	self.ignoreEvents = 1
	iter = self.ethdevices.store.get_iter_first()
	selection = self.ethdevices.get_selection()
	selection.set_mode(gtk.SELECTION_BROWSE)
	selection.select_iter(iter)
	self.ignoreEvents = 0

	return self.ethdevices

    def modifyHostname(self, widget):
	if self.ignoreEvents:
	    return

        editWin = gtk.Dialog(flags=gtk.DIALOG_MODAL)
        gui.addFrame(editWin)
        editWin.set_modal(gtk.TRUE)

	vbox = gtk.VBox()
	hbox = gtk.HBox()
	hbox.pack_start(gtk.Label(_("Hostname")), gtk.FALSE, gtk.FALSE)
	hentry = gtk.Entry()
	hbox.pack_start(hentry, gtk.FALSE, gtk.FALSE)
	vbox.pack_start(hbox, gtk.FALSE, gtk.FALSE)
	vbox.set_border_width(6)
	frame = gtk.Frame(_("Set hostname"))
	frame.add(vbox)
	frame.set_border_width(3)
	editWin.vbox.pack_start(frame, padding=5)
        editWin.set_position(gtk.WIN_POS_CENTER)
	editWin.show_all()
        editWin.add_button('gtk-cancel', 2)
	editWin.add_button('gtk-ok', 1)

	while 1:
	    rc=editWin.run()
	    
	    if rc == 2:
		editWin.destroy()
		return

	    h = string.strip(hentry.get_text())
	    if len(h) > 0:
		self.hostname = h

	    editWin.destroy()

	    return

    def hostnameUseDHCPCB(self, widget, data):
	self.hostnameEntry.set_sensitive(not widget.get_active())

    def hostnameManualCB(self, widget, data):
	if widget.get_active():
	    self.hostnameEntry.grab_focus()

    # NetworkWindow tag="netconf"
    def getScreen(self, network, dispatch, intf):
	self.intf = intf
        box = gtk.VBox(gtk.FALSE)
        box.set_border_width(5)
	self.network = network
        
        self.devices = self.network.available()
	
        if not self.devices:
	    return None

	self.numdevices = len(self.devices.keys())

	self.hostname = self.network.hostname

	devhbox = gtk.HBox(gtk.FALSE)

	self.devlist = self.setupDevices()

	devlistSW = gtk.ScrolledWindow()
        devlistSW.set_border_width(5)
        devlistSW.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        devlistSW.set_shadow_type(gtk.SHADOW_IN)
        devlistSW.add(self.devlist)
	devlistSW.set_size_request(-1, 150)
	devhbox.pack_start(devlistSW, gtk.FALSE, padding=10)

        buttonbar = gtk.VButtonBox()
        buttonbar.set_layout(gtk.BUTTONBOX_START)
        buttonbar.set_border_width(5)
	edit = gtk.Button(_("_Edit"))
        edit.connect("clicked", self.editDevice)
	buttonbar.pack_start(edit, gtk.FALSE)
	devhbox.pack_start(buttonbar, gtk.FALSE)

	devhbox.set_border_width(6)
	frame=gtk.Frame(_("Network Devices"))
	frame.add(devhbox)
	box.pack_start(frame, gtk.FALSE)
	
	# show hostname and dns/misc network info and offer chance to modify
	hostbox = gtk.HBox()
	hostbox=gtk.VBox()
	label=gtk.Label(_("Set the hostname:"))
	label.set_alignment(0.0, 0.0)
	hostbox.pack_start(label, gtk.FALSE, gtk.FALSE)
	tmphbox=gtk.HBox()
        self.hostnameUseDHCP = gtk.RadioButton(label=_("_automatically via DHCP"))
	self.hostnameUseDHCP.connect("toggled", self.hostnameUseDHCPCB, None)
	
	tmphbox.pack_start(self.hostnameUseDHCP, gtk.FALSE, gtk.FALSE, padding=15)
	hostbox.pack_start(tmphbox, gtk.FALSE, gtk.FALSE, padding=5)

	self.hostnameManual  = gtk.RadioButton(group=self.hostnameUseDHCP, label=_("_manually"))
	tmphbox=gtk.HBox()
	tmphbox.pack_start(self.hostnameManual, gtk.FALSE, gtk.FALSE, padding=15)
	self.hostnameEntry = gtk.Entry()
	    
	tmphbox.pack_start(self.hostnameEntry, gtk.FALSE, gtk.FALSE, padding=15)
	self.hostnameManual.connect("toggled", self.hostnameManualCB, None)

	hostbox.pack_start(tmphbox, gtk.FALSE, gtk.FALSE, padding=5)

	hostbox.set_border_width(6)
	frame=gtk.Frame(_("Hostname"))
	frame.add(hostbox)
	box.pack_start(frame, gtk.FALSE, gtk.FALSE)


        # figure out if they have overridden using dhcp for hostname
	# print self.anyUsingDHCP()
	if self.anyUsingDHCP():
	    if self.hostname != "localhost.localdomain" and self.network.overrideDHCPhostname:
		self.hostnameManual.set_active(1)
	    else:
		self.hostnameUseDHCP.set_active(1)
	else:
	    self.hostnameManual.set_active(1)

        #
	# this is the iptable used for DNS, et. al
	self.ipTable = gtk.Table(len(global_options), 2)
#	self.ipTable.set_row_spacing(0, 5)
	options = {}
	for i in range(len(global_options)):
	    label = gtk.Label("%s:" %(global_option_labels[i],))
	    label.set_property("use-underline", gtk.TRUE)
	    label.set_alignment(0.0, 0.0)
	    self.ipTable.attach(label, 0, 1, i, i+1, gtk.FILL, 0)
	    align = gtk.Alignment(0, 0.5)
	    options[i] = ipwidget.IPEditor()
	    align.add(options[i].getWidget())
	    label.set_mnemonic_widget(options[i].getFocusableWidget())

	    self.ipTable.attach(align, 1, 2, i, i+1, gtk.FILL, 0)


	self.globals = {}
	for t in range(len(global_options)):
	    self.globals[global_options[t]] = options[t]

	# bring over the value from the loader
	if self.network.hostname != "localhost.localdomain" and ((self.anyUsingDHCP() and self.network.overrideDHCPhostname) or not self.anyUsingDHCP()):
	    self.hostnameEntry.set_text(self.network.hostname)

#
# for now always put info in the entries, even if we're using DHCP
#
#	if not self.anyUsingDHCP() or 1:
        if 1:
	    if self.network.gateway:
		self.globals[_("Gateway")].hydrate(self.network.gateway)
	    if self.network.primaryNS:
		self.globals[_("Primary DNS")].hydrate(self.network.primaryNS)
	    if self.network.secondaryNS:
		self.globals[_("Secondary DNS")].hydrate(self.network.secondaryNS)
	    if self.network.ternaryNS:
		self.globals[_("Tertiary DNS")].hydrate(self.network.ternaryNS)

	self.ipTable.set_border_width(6)

	frame=gtk.Frame(_("Miscellaneous Settings"))
	frame.add(self.ipTable)
	box.pack_start(frame, gtk.FALSE, gtk.FALSE, 5)
	box.set_border_width(6)

	self.hostnameEntry.set_sensitive(not self.hostnameUseDHCP.get_active())
	self.setIPTableSensitivity()
	self.setHostOptionsSensitivity()

	return box


class NetworkDeviceCheckList(checklist.CheckList):
    def toggled_item(self, data, row):
	checklist.CheckList.toggled_item(self, data, row)

	if self.clickCB:
	    rc = self.clickCB(data, row)
    
    def __init__(self, columns, clickCB=None):
	checklist.CheckList.__init__(self, columns=columns)

	self.clickCB = clickCB
