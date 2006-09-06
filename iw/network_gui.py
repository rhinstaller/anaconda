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

global_options = [_("Gateway"), _("Primary DNS"), _("Secondary DNS")]
global_option_labels = [_("_Gateway"), _("_Primary DNS"), _("_Secondary DNS")]

descr = { 'ipaddr':   'IPv4 address',
          'netmask':  'IPv4 network mask',
          'remip':    'point-to-point IP address',
          'ipv6addr': 'IPv6 address'
        }

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
                    network.sanityCheckIPString(self.globals[global_options[t]].get_text())
		    tmpvals[t] = self.globals[global_options[t]].get_text()
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
	elif self.id.instClass.name != "kickstart":
	    self.network.gateway = None
	    self.network.primaryNS = None
	    self.network.secondaryNS = None

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
	try:
	    newfield = descr[field]
	except:
	    newfield = field

	self.intf.messageWindow(_("Error With Data"),
				_("A value is required for the field \"%s\".") % (newfield,))

    def handleBroadCastError(self):
	self.intf.messageWindow(_("Error With Data"),
				_("The IP information you have entered is "
				  "invalid."))

    def handleNoActiveDevices(self):
	return self.intf.messageWindow(_("Error With Data"), _("You have no active network devices.  Your system will not be able to communicate over a network by default without at least one device active."), type="custom", custom_buttons=["gtk-cancel", _("C_ontinue")])
    
    def editDevice(self, data):
	v4list = []
	v6list = []
	ptplist = []
	wifilist = []

        def DHCPtoggled(widget):
	    active = widget.get_active()

	    if wifilist:
	        for widget in wifilist:
	            widget.set_sensitive(True)

	    if active:
	        bootproto = "dhcp"

	        for widget in v4list:
	            widget.set_sensitive(False)

	        for widget in v6list:
	            widget.set_sensitive(False)

	        if ptplist:
	            for widget in ptplist:
	                widget.set_sensitive(False)
	    else:
	        bootproto = "static"

	        if IPV4cb.get_active():
	            for widget in v4list:
	                widget.set_sensitive(True)

	        if IPV6cb.get_active():
	            for widget in v6list:
	                widget.set_sensitive(True)

	        if ptplist:
	            for widget in ptplist:
	                widget.set_sensitive(True)

	def IPV4toggled(widget):
	    active = widget.get_active()
	    if not DHCPcb.get_active():
	        if active:
	            for widget in v4list:
	                widget.set_sensitive(True)
	        else:
	            for widget in v4list:
	                widget.set_sensitive(False)

	def IPV6toggled(widget):
	    active = widget.get_active()
	    if not DHCPcb.get_active():
	        if active:
	            for widget in v6list:
	                widget.set_sensitive(True)
	        else:
	            for widget in v6list:
	                widget.set_sensitive(False)


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
        editWin.set_position (gtk.WIN_POS_CENTER)
	
	# create contents
	devbox = gtk.VBox()

	hwaddr = self.devices[dev].get("hwaddr")
	if hwaddr is not None and len(hwaddr) > 0:
	    align = gtk.Alignment()
	    label = gtk.Label(_("Hardware address: %s") % (hwaddr,))
	    align.add(label)
	    devbox.pack_start(align, False, padding=3)

	align = gtk.Alignment()
	DHCPcb = gtk.CheckButton(_("Use dynamic IP configuration (_DHCP)"))
	align.add(DHCPcb)
	devbox.pack_start(align, False, padding=3)

	align = gtk.Alignment()
	IPV4cb = gtk.CheckButton(_("Enable IPv4 support"))
	align.add(IPV4cb)
	devbox.pack_start(align, False, padding=3)

	align = gtk.Alignment()
	IPV6cb = gtk.CheckButton(_("Enable IPv6 support"))
	align.add(IPV6cb)
	devbox.pack_start(align, False, padding=3)

	align = gtk.Alignment()
	bootcb = gtk.CheckButton(_("_Activate on boot"))

	bootcb.connect("toggled", self.onBootToggled, self.devices[dev])
	bootcb.set_active(onboot)
	align.add(bootcb)
	devbox.pack_start(align, False, padding=3)

        ipTableLength = 2

        if (network.isPtpDev(dev)):
            ipTableLength += 1

        if (isys.isWireless(dev)):
            ipTableLength += 2

        ipTable = gtk.Table(ipTableLength, 4)

	DHCPcb.connect("toggled", DHCPtoggled)

	IPV4cb.connect("toggled", IPV4toggled)
	IPV4cb.set_active(True)

	IPV6cb.connect("toggled", IPV6toggled)
	IPV6cb.set_active(True)

	entrys = {}

        # build the IP options table:

        # IPv4 address and mask
        v4list.append(gtk.Label(_("IPv_4 Address:")))
        v4list[0].set_alignment(0.0, 0.5)
        v4list[0].set_property("use_underline", True)
        ipTable.attach(v4list[0], 0, 1, 1, 2, xpadding=0, ypadding=0)

        v4list.append(gtk.Entry())
	v4list[1].set_width_chars(16)
        entrys['ipaddr'] = v4list[1]
        ipTable.attach(v4list[1], 1, 2, 1, 2, xpadding=0, ypadding=0)

        v4list.append(gtk.Label("/"))
        v4list[2].set_alignment(0.0, 0.5)
        ipTable.attach(v4list[2], 2, 3, 1, 2, xpadding=4, ypadding=0)

        v4list.append(gtk.Entry())
	v4list[3].set_width_chars(16)
        entrys['netmask'] = v4list[3]
        ipTable.attach(v4list[3], 3, 4, 1, 2, xpadding=0, ypadding=0)

        # IPv6 address and prefix
        v6list.append(gtk.Label(_("IPv_6 Address:")))
        v6list[0].set_alignment(0.0, 0.5)
        v6list[0].set_property("use_underline", True)
        ipTable.attach(v6list[0], 0, 1, 2, 3, xpadding=0, ypadding=0)

        v6list.append(gtk.Entry())
	v6list[1].set_width_chars(41)
        entrys['ipv6addr'] = v6list[1]
        ipTable.attach(v6list[1], 1, 2, 2, 3, xpadding=0, ypadding=0)

        v6list.append(gtk.Label("/"))
        v6list[2].set_alignment(0.0, 0.5)
        ipTable.attach(v6list[2], 2, 3, 2, 3, xpadding=4, ypadding=0)

        v6list.append(gtk.Entry())
	v6list[3].set_width_chars(4)
        entrys['ipv6prefix'] = v6list[3]
        ipTable.attach(v6list[3], 3, 4, 2, 3, xpadding=0, ypadding=0)

        # Point to Point address
        if (network.isPtpDev(dev)):
            ptplist.append(gtk.Label(_("_Point to Point (IP):")))
            ptplist[0].set_alignment(0.0, 0.5)
            ptplist[0].set_property("use_underline", True)
            ipTable.attach(ptplist[0], 0, 1, 3, 4, xpadding=0, ypadding=0)

            ptplist.append(gtk.Entry())
	    ptplist[1].set_width_chars(41)
            entrys['remip'] = ptplist[1]
            ipTable.attach(ptplist[1], 1, 2, 3, 4, xpadding=0, ypadding=0)

        if (isys.isWireless(dev)):
            wifilist.append(gtk.Label(_("_ESSID:")))
            wifilist[0].set_alignment(0.0, 0.5)
            wifilist[0].set_property("use_underline", True)
            ipTable.attach(wifilist[0], 0, 1, 4, 5, xpadding=0, ypadding=0)

            wifilist.append(gtk.Entry())
            entrys['essid'] = wifilist[1]
            ipTable.attach(wifilist[1], 1, 2, 4, 5, xpadding=0, ypadding=0)

            wifilist.append(gtk.Label(_("Encryption _Key:")))
            wifilist[2].set_alignment(0.0, 0.5)
            wifilist[2].set_property("use_underline", True)
            ipTable.attach(wifilist[2], 0, 1, 5, 6, xpadding=0, ypadding=0)

            wifilist.append(gtk.Entry())
            entrys['key'] = wifilist[3]
            ipTable.attach(wifilist[3], 1, 2, 5, 6, xpadding=0, ypadding=0)

	devbox.pack_start(ipTable, False, False, 6)
        devbox.set_border_width(6)

	# go ahead and set up DHCP on the first device
	DHCPcb.set_active(bootproto == 'DHCP')

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
		for t in entrys.keys():
		    if t == "ipaddr" or t == "netmask" or t == "remip" or t == "ipv6addr":
		        try:
		            network.sanityCheckIPString(entrys[t].get_text())
		            tmpvals[t] = entrys[t].get_text()
		        except network.IPMissing, msg:
		            self.handleIPMissing(t)
		            valsgood = 0
		            break

		if valsgood == 0:
		    continue

		try:
                    (net, bc) = isys.inet_calcNetBroad (tmpvals['ipaddr'],
                                                        tmpvals['netmask'])
		except Exception, e:
                    print e
		    self.handleBroadCastError()
		    valsgood = 0

		if not valsgood:
		    continue

		for t in entrys.keys():
		    if t == 'ipv6prefix':
		        continue

		    if tmpvals.has_key(t):
		        if t == 'ipv6addr':
		            if entrys['ipv6prefix'] is not None:
		                q = "%s/%s" % (tmpvals[t],entrys['ipv6prefix'],)
		            else:
		                q = "%s" % (tmpvals[t],)

		            self.devices[dev].set((t, q))
		        else:
		            self.devices[dev].set((t, tmpvals[t]))
		    else:
		        self.devices[dev].set((t, entrys[t].get_text()))

		self.devices[dev].set(('network', net), ('broadcast', bc))

	    self.devices[dev].set(('bootproto', bootproto))
	    self.devices[dev].set(('ONBOOT', onboot))
	    model.set_value(iter, 0, onboot == 'yes')
	    model.set_value(iter, 2, self.createIPV4Repr(self.devices[dev]))
	    model.set_value(iter, 3, self.createIPV6Repr(self.devices[dev]))

	    editWin.destroy()

	    self.setIPTableSensitivity()
	    self.setHostOptionsSensitivity()

	    return

    def createIPV4Repr(self, device):
	bootproto = device.get("bootproto")
	if bootproto == "dhcp":
	    ip = "DHCP"
	else:
	    prefix = isys.inet_convertNetmaskToPrefix(device.get("netmask"))
	    ip = "%s/%s" % (device.get("ipaddr"), prefix,)

	return ip

    def createIPV6Repr(self, device):
	bootproto = device.get("bootproto")
	if bootproto == "dhcp":
	    ip = "DHCP"
	else:
	    ip = "%s" % (device.get("ipv6addr"),)

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
			  gobject.TYPE_STRING,
			  gobject.TYPE_STRING)
	
	self.ethdevices = NetworkDeviceCheckList(3, store, clickCB=self.onbootToggleCB)
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
		
	    ipv4 = self.createIPV4Repr(self.devices[device])
	    ipv6 = self.createIPV6Repr(self.devices[device])

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
            self.ethdevices.append_row((device, ipv4, ipv6), active)

            num += 1

	self.ethdevices.set_column_title(0, (_("Active on Boot")))
        self.ethdevices.set_column_sizing (0, gtk.TREE_VIEW_COLUMN_GROW_ONLY)
	self.ethdevices.set_column_title(1, (_("Device")))
        self.ethdevices.set_column_sizing (1, gtk.TREE_VIEW_COLUMN_GROW_ONLY)
	self.ethdevices.set_column_title(2, (_("IPv4/Netmask")))
        self.ethdevices.set_column_sizing (2, gtk.TREE_VIEW_COLUMN_GROW_ONLY)
        self.ethdevices.set_column_title (3, (_("IPv6/Prefix")))
        self.ethdevices.set_column_sizing (3, gtk.TREE_VIEW_COLUMN_GROW_ONLY)
#	self.ethdevices.set_column_title(4, (_("Description")))
#        self.ethdevices.set_column_sizing (4, gtk.TREE_VIEW_COLUMN_GROW_ONLY)
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
	    self.globals[global_options[t]] = options[t]

	# bring over the value from the loader
	self.hostnameEntry.set_text(self.network.hostname)

	if not self.anyUsingDHCP():
	    if self.network.gateway:
                self.globals[_("Gateway")].set_text(self.network.gateway)
	    if self.network.primaryNS:
                self.globals[_("Primary DNS")].set_text(self.network.primaryNS)
	    if self.network.secondaryNS:
                self.globals[_("Secondary DNS")].set_text(self.network.secondaryNS)

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
