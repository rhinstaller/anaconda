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

global_options = [_("Hostname"), _("Gateway"), _("Primary DNS"),
		  _("Secondary DNS"), _("Tertiary DNS")]

class NetworkWindow(InstallWindow):		

    windowTitle = N_("Network Configuration")
    htmlTag = "netconf"

    def __init__(self, ics):
	InstallWindow.__init__(self, ics)

    def getNext(self):
	# XXX huh?
#	if not self.__dict__.has_key("gw"):
#	    return None

	tmpvals = {}
	for t in range(len(global_options)):
	    if t == 0:
		tmpvals[t] = string.strip(self.hostname.get_text())
		neterrors =  network.sanityCheckHostname(tmpvals[t])
		if neterrors is not None:
		    self.handleBadHostname(tmpvals[t], neterrors)
		    raise gui.StayOnScreen
	    else:
		try:
		    tmpvals[t] = self.globals[global_options[t]].dehydrate()
		except ipwidget.IPError, msg:
		    tmpvals[t] = None
		    pass
#		    self.handleIPError(global_options[t], msg[0])
#		    raise gui.StayOnScreen 

        if(tmpvals[0] != ""):
            self.network.hostname = string.strip(tmpvals[0])

	if tmpvals[1]:
	    self.network.gateway = tmpvals[1]
	if tmpvals[2]:
	    self.network.primaryNS = tmpvals[2]
	if tmpvals[3]:
	    self.network.secondaryNS = tmpvals[3]
	if tmpvals[4]:
	    self.network.ternaryNS = tmpvals[4]
            
        iter = self.ethdevices.store.get_iter_root()
	next = 1
	while next:
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
            next = self.ethdevices.store.iter_next(iter)

        return None
        
    def DHCPtoggled(self, widget, (dev, table)):
	active = widget.get_active()
        table.set_sensitive(not active)
        self.ipTable.set_sensitive(not active)
	
	bootproto = "dhcp"
	if not active:
            bootproto = "static"
	dev.set(("bootproto", bootproto))

    def onBootToggled(self, widget, dev):
	if widget.get_active():
	    onboot = "yes"
	else:
	    onboot = "no"
	dev.set(("ONBOOT", onboot))

    def handleBadHostname(self, hostname, error):
	self.intf.messageWindow(_("Error With Data"),
				_("The hostname \"%s\" is not valid for the following reason:\n\n%s") % (hostname, error))

    def handleIPError(self, field, errmsg):
	self.intf.messageWindow(_("Error With Data"),
				_("An error occurred converting "
				  " the value entered for %s:\n\n%s" % (field, errmsg)))

    def handleBroadCastError(self):
	self.intf.messageWindow(_("Error With Data"),
				_("The IP information you have entered is "
				  "invalid."))

    def editDevice(self, data):
	if self.ignoreEvents:
	    return
	
	selection = self.ethdevices.get_selection()
        rc = selection.get_selected()
        if not rc:
            return None
        model, iter = rc

        dev = model.get_value(iter, 1)
	bootproto = model.get_value(iter, 2)
	onboot = model.get_value(iter, 0)

	# create dialog box
        editWin = gtk.Dialog(flags=gtk.DIALOG_MODAL)
        gui.addFrame(editWin)
        editWin.set_modal(gtk.TRUE)
#        editWin.set_size_request(350, 200)
        editWin.set_position (gtk.WIN_POS_CENTER)
	
	# create contents
	devbox = gtk.VBox()
	align = gtk.Alignment()
	DHCPcb = gtk.CheckButton(_("Configure using DHCP"))

	align.add(DHCPcb)
	devbox.pack_start(align, gtk.FALSE)

	align = gtk.Alignment()
	bootcb = gtk.CheckButton(_("Activate on boot"))

	bootcb.connect("toggled", self.onBootToggled, self.devices[dev])
	bootcb.set_active(onboot)
	align.add(bootcb)

	devbox.pack_start(align, gtk.FALSE)
	devbox.pack_start(gtk.HSeparator(), gtk.FALSE, padding=3)

	options = [(_("IP Address"), "ipaddr"),
		   (_("Netmask"),    "netmask")]

	if len(dev) >= 3 and dev[:3] == 'ctc':
	    newopt = (_("Point to Point (IP)"), "remip")
	    options.append(newopt)
            
        ipTable = gtk.Table(len(options), 2)
	DHCPcb.connect("toggled", self.DHCPtoggled, (self.devices[dev], ipTable))
	# go ahead and set up DHCP on the first device
	DHCPcb.set_active(bootproto == 'DHCP')
	entrys = {}
	for t in range(len(options)):
	    label = gtk.Label("%s:" %(options[t][0],))
	    label.set_alignment(0.0, 0.5)
	    ipTable.attach(label, 0, 1, t, t+1, gtk.FILL, 0, 10)

	    entry = ipwidget.IPEditor()
	    entry.hydrate(self.devices[dev].get(options[t][1]))
	    entrys[t] = entry
	    ipTable.attach(entry.getWidget(), 1, 2, t, t+1, 0, gtk.FILL|gtk.EXPAND)

	devbox.pack_start(ipTable, gtk.FALSE, gtk.FALSE, 5)

	frame = gtk.Frame(_("Configure %s" % (dev,)))
	frame.add(devbox)
	editWin.vbox.pack_start(frame, padding=5)
        editWin.set_position(gtk.WIN_POS_CENTER)
	editWin.show_all()
	editWin.add_button('gtk-ok', 1)
        editWin.add_button('gtk-cancel', 2)

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
		    except ipwidget.IPError, msg:
			self.handleIPError(options[t][1], msg[0])
			valsgood = 0

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
	    return

    def createIPRepr(self, device):
	bootproto = device.get("bootproto")
	if bootproto == "dhcp":
	    ip = "DHCP"
	else:
	    ip = "%s/%s" % (device.get("ipaddr"), device.get("netmask"))

	return ip

    def setupDevices(self):
	devnames = self.devices.keys()
	devnames.sort()

	self.ethdevices = checklist.CheckList(2)

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
	iter = self.ethdevices.store.get_iter_root()
	selection = self.ethdevices.get_selection()
	selection.set_mode(gtk.SELECTION_BROWSE)
	selection.select_iter(iter)
	self.ignoreEvents = 0

	return self.ethdevices


    # NetworkWindow tag="netconf"
    def getScreen(self, network, dispatch, intf):
	self.intf = intf
        box = gtk.VBox(gtk.FALSE)
        box.set_border_width(5)
	self.network = network
        
        self.devices = self.network.available()
        if not self.devices:
	    return None

	devhbox = gtk.HBox(gtk.FALSE)

	self.devlist = self.setupDevices()

	devlistSW = gtk.ScrolledWindow()
        devlistSW.set_border_width(5)
        devlistSW.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        devlistSW.set_shadow_type(gtk.SHADOW_IN)
        devlistSW.add(self.devlist)
	devlistSW.set_size_request(-1, 175)
	devhbox.pack_start(devlistSW, gtk.FALSE, padding=10)

        buttonbar = gtk.VButtonBox()
        buttonbar.set_layout(gtk.BUTTONBOX_START)
        buttonbar.set_border_width(5)
	edit = gtk.Button(_("_Edit"))
        edit.connect("clicked", self.editDevice)
	buttonbar.pack_start(edit, gtk.FALSE)
	devhbox.pack_start(buttonbar, gtk.FALSE)
	
	box.pack_start(devhbox, gtk.FALSE, padding=10)
	
        box.pack_start(gtk.HSeparator(), gtk.FALSE, padding=10)

	# this is the iptable used for DNS, et. al
	self.ipTable = gtk.Table(len(global_options), 2)
	options = {}
        for i in range(len(global_options)):
            label = gtk.Label("%s:" %(global_options[i],))
            label.set_alignment(0.0, 0.0)
            self.ipTable.attach(label, 0, 1, i, i+1, gtk.FILL, 0, 10)
            align = gtk.Alignment(0, 0.5)
            if i == 0:
                options[i] = gtk.Entry()
                options[i].set_size_request(7 * 30, -1)
		align.add(options[i])
            else:
                options[i] = ipwidget.IPEditor()
		align.add(options[i].getWidget())

            self.ipTable.attach(align, 1, 2, i, i+1, gtk.FILL, 0)
        self.ipTable.set_row_spacing(0, 5)

	self.globals = {}
	for t in range(len(global_options)):
	    if t == 0:
		self.hostname = options[0]
	    else:
		self.globals[global_options[t]] = options[t]

        # bring over the value from the loader
        if(self.network.hostname != "localhost.localdomain"):
            self.hostname.set_text(self.network.hostname)

        self.globals[_("Gateway")].hydrate(self.network.gateway)
        self.globals[_("Primary DNS")].hydrate(self.network.primaryNS)
        self.globals[_("Secondary DNS")].hydrate(self.network.secondaryNS)
        self.globals[_("Tertiary DNS")].hydrate(self.network.ternaryNS)
	
        box.pack_start(self.ipTable, gtk.FALSE, gtk.FALSE, 5)

        return box

