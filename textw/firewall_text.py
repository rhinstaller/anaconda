from snack import *
from constants_text import *
from translate import _
import iutil

class FirewallWindow:
    def __call__(self, screen, todo):
	
	instType = todo.instClass.installType
	if instType == "custom" or todo.expert or instType == "server":
	    detail = 1
	else:
	    detail = 0
	
	bb = ButtonBar (screen, ((_("OK"), "ok"), (_("Back"), "back")))
	
	toplevel = GridFormHelp (screen, _("Firewall Configuration"),
				"firewall", 1, 5)
	text = _("A firewall protects against unauthorized "
		 "network intrusions. High security blocks all "
		 "incoming accesses. Medium blocks access "
		 "to system services (such as telnet or printing), "
		 "but allows other connections. No firewall allows "
		 "all connections and is not recommended. ")
	toplevel.add (TextboxReflowed(65, text), 0, 0, (0, 0, 0, 1))	 
						
	toplevel.add (bb, 0, 4, (0, 0, 0, 0), growx = 1)
	
	bigGrid = Grid(2,15)
	
	typeGrid = Grid(3,2)

	label = Label(_("Security Level:"))
	bigGrid.setField (label, 0, 0, (0, 0, 0, 1), anchorLeft = 1)
	
	
	self.paranoid = SingleRadioButton(_("High"), None, todo.firewall.enabled and not todo.firewall.policy)
	self.paranoid.setCallback(self.radiocb, (todo, self.paranoid))
	typeGrid.setField (self.paranoid, 0, 0, (0, 0, 1, 0), anchorLeft = 1)
	self.simple = SingleRadioButton(_("Medium"), self.paranoid, todo.firewall.enabled and todo.firewall.policy)
	self.simple.setCallback(self.radiocb, (todo, self.simple))
	typeGrid.setField (self.simple, 1, 0, (0, 0, 1, 0), anchorLeft = 1)
	self.disabled = SingleRadioButton(_("No firewall"), self.simple, not todo.firewall.enabled)
	self.disabled.setCallback(self.radiocb, (todo, self.disabled))
	typeGrid.setField (self.disabled, 2, 0, (0, 0, 1, 0), anchorLeft = 1)
	
	self.customize = Checkbox(_("Customize"), detail)
	self.customize.setCallback(self.customcb, (todo, self.customize))
	typeGrid.setField (self.customize, 0, 1, (0, 0, 1, 0), anchorLeft = 1)
	
	bigGrid.setField(typeGrid, 1, 0, (1, 0, 0, 1), anchorLeft = 1)
	
	currentRow = 1
	devices = todo.network.available().keys()
	self.netCBs = {}
	if (devices):
	    devices.sort()
	    cols = len(devices)
	    if cols > 4:
		rows = cols % 4
		cols = 4
	    else:
		rows = 1
	    self.devGrid = Grid(cols, rows)

	    bigGrid.setField (Label(_("Trusted Devices:")), 0, currentRow, (0, 0, 0, 1),
	    		anchorLeft = 1)
	    curcol = 0
	    currow = 0
	    for dev in devices:
		if todo.network.netdevices[dev].get('bootproto') == 'dhcp':
		    todo.firewall.dhcp = 1
		cb = Checkbox (dev, dev in todo.firewall.trustdevs)
		self.devGrid.setField(cb, curcol, currow, (0, 0, 1, 0), anchorLeft = 1)
 		self.netCBs[dev] = cb
		curcol = curcol + 1
		if curcol >= cols:
		    currow = currow + 1
		    curcol = 1
	    bigGrid.setField (self.devGrid, 1, currentRow, (1, 0, 0, 1), anchorLeft = 1)
	    currentRow = currentRow + 1
	
	bigGrid.setField (Label(_("Allow incoming:")), 0, currentRow, (0, 0, 0, 1),
		anchorTop = 1)
	    
	self.portGrid = Grid(2,4)
	    
	self.dhcp = Checkbox (_("DHCP"), todo.firewall.dhcp)
	self.portGrid.setField (self.dhcp, 0, 0, (0, 0, 1, 0), anchorLeft = 1)
	self.ssh = Checkbox (_("SSH (Secure Shell)"), todo.firewall.ssh)
	self.portGrid.setField (self.ssh, 1, 0, (0, 0, 1, 0), anchorLeft = 1)
	self.telnet = Checkbox (_("Telnet"), todo.firewall.telnet)
	self.portGrid.setField (self.telnet, 0, 1, (0, 0, 1, 0), anchorLeft = 1)
	self.http = Checkbox (_("WWW (HTTP)"), todo.firewall.http)
	self.portGrid.setField (self.http, 1, 1, (0, 0, 1, 0), anchorLeft = 1)
	self.smtp = Checkbox (_("Mail (SMTP)"), todo.firewall.smtp)
	self.portGrid.setField (self.smtp, 0, 2, (0, 0, 1, 0), anchorLeft = 1)
	self.ftp = Checkbox (_("FTP"), todo.firewall.ftp)
	self.portGrid.setField (self.ftp, 1, 2, (0, 0, 1, 0), anchorLeft = 1)
	
	self.portGrid.setField (Label(_("Other ports")), 0, 3, (0, 0, 1, 0), anchorLeft = 1)
	self.other = Entry (25, todo.firewall.portlist)
	self.portGrid.setField (self.other, 1, 3, (0, 0, 1, 0), anchorLeft = 1)
    
	bigGrid.setField (self.portGrid, 1, currentRow, (1, 0, 0, 1), anchorLeft = 1)
	
	self.portboxes = ( self.ssh, self.telnet, self.http, self.smtp, self.ftp,
		self.other )
		
	toplevel.add(bigGrid, 0, 1, (0, 0, 0, 0), anchorLeft = 1)
	if self.disabled.selected():
	    self.radiocb((todo, self.disabled))
	self.customcb((todo, self.customize))

	result = toplevel.runOnce ()
	rc = bb.buttonPressed (result)
	
        if rc == "back":
	    return INSTALL_BACK
	
	for device in self.netCBs.keys():
	    if self.netCBs[device].selected():
		todo.firewall.trustdevs.append(device)
	print todo.firewall.trustdevs
	todo.firewall.portlist = self.other.value()
	todo.firewall.dhcp = self.dhcp.selected()
	todo.firewall.ssh = self.ssh.selected()
	todo.firewall.telnet = self.telnet.selected()
	todo.firewall.http = self.http.selected()
	todo.firewall.smtp = self.smtp.selected()
	todo.firewall.ftp = self.ftp.selected()
	if self.disabled.selected():
	    todo.firewall.enabled = 0
	else:
	    todo.firewall.enabled = 1
	if self.paranoid.selected():
	    todo.firewall.policy = 0
	else:
	    todo.firewall.policy = 1
	return INSTALL_OK
    
    def customcb(self, args):
	(todo, wigdet) = args
	if self.customize.selected():
	    flag = FLAGS_RESET
	else:
	    flag = FLAGS_SET
	self.dhcp.setFlags(FLAG_DISABLED, flag)
	for cb in self.portboxes:
	    cb.setFlags(FLAG_DISABLED, flag)
	for cb in self.netCBs.values():
	    cb.setFlags(FLAG_DISABLED, flag)
			
    def radiocb(self, args):
	(todo, widget) = args
	if widget == self.disabled:
	    todo.firewall.enabled = 0
	    self.customize.setFlags(FLAG_DISABLED, FLAGS_SET)
	    for cb in self.portboxes:
		cb.setFlags(FLAG_DISABLED, FLAGS_SET)
	    for cb in self.netCBs.values():
		cb.setFlags(FLAG_DISABLED, FLAGS_SET)
	    self.dhcp.setFlags(FLAG_DISABLED, FLAGS_SET)
	elif widget == self.simple:
	    todo.firewall.policy = 1
	    for cb in self.portboxes:
		cb.setFlags(FLAG_DISABLED, FLAGS_RESET)
	    for cb in self.netCBs.values():
		cb.setFlags(FLAG_DISABLED, FLAGS_RESET)
	    self.customize.setFlags(FLAG_DISABLED, FLAGS_RESET)
	    self.dhcp.setFlags(FLAG_DISABLED, FLAGS_RESET)
	elif widget == self.paranoid:
	    todo.firewall.policy = 0
	    for cb in self.portboxes:
		cb.setFlags(FLAG_DISABLED, FLAGS_RESET)
	    for cb in self.netCBs.values():
		cb.setFlags(FLAG_DISABLED, FLAGS_RESET)
	    self.customize.setFlags(FLAG_DISABLED, FLAGS_RESET)
	    self.dhcp.setFlags(FLAG_DISABLED, FLAGS_RESET)
	else:
	    raise RuntimeError, "never reached"

