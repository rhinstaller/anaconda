from snack import *
from constants_text import *
from translate import _
import iutil

class FirewallWindow:
    def __call__(self, screen, todo):
	
	bb = ButtonBar (screen, ((_("OK"), "ok"), (_("Customize"), "customize"), (_("Back"), "back")))
	
	toplevel = GridFormHelp (screen, _("Firewall Configuration"),
				"securitylevel", 1, 5)
	text = _("A firewall protects against unauthorized "
		 "network intrusions. High security blocks all "
		 "incoming accesses. Medium blocks access "
		 "to system services (such as telnet or printing), "
		 "but allows other connections. No firewall allows "
		 "all connections and is not recommended. ")
	toplevel.add (TextboxReflowed(50, text), 0, 0, (0, 0, 0, 1))	 
						
	toplevel.add (bb, 0, 4, (0, 0, 0, 0), growx = 1)
	
	smallGrid = Grid(2,1)
	
	bigGrid = Grid(2,15)
	
	typeGrid = Grid(3,2)

	label = Label(_("Security Level:"))
	smallGrid.setField (label, 0, 0, (0, 0, 0, 1), anchorLeft = 1)
	
	
	self.paranoid = SingleRadioButton(_("High"), None, todo.firewall.enabled and not todo.firewall.policy)
	self.paranoid.setCallback(self.radiocb, (todo, self.paranoid))
	typeGrid.setField (self.paranoid, 0, 0, (0, 0, 1, 0), anchorLeft = 1)
	self.simple = SingleRadioButton(_("Medium"), self.paranoid, todo.firewall.enabled and todo.firewall.policy)
	self.simple.setCallback(self.radiocb, (todo, self.simple))
	typeGrid.setField (self.simple, 1, 0, (0, 0, 1, 0), anchorLeft = 1)
	self.disabled = SingleRadioButton(_("No firewall"), self.simple, not todo.firewall.enabled)
	self.disabled.setCallback(self.radiocb, (todo, self.disabled))
	typeGrid.setField (self.disabled, 2, 0, (0, 0, 1, 0), anchorLeft = 1)
	
	smallGrid.setField (typeGrid, 1, 0, (1, 0, 0, 1), anchorLeft = 1)
	
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

            if devices != []:
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



	
	bigGrid.setField (Label(_("Allow incoming:")), 0, currentRow, (0, 0, 0, 0),
		anchorTop = 1)
	    
	self.portGrid = Grid(3,2)
	    
	self.dhcp = Checkbox (_("DHCP"), todo.firewall.dhcp)
	self.portGrid.setField (self.dhcp, 0, 0, (0, 0, 1, 0), anchorLeft = 1)
	self.ssh = Checkbox (_("SSH"), todo.firewall.ssh)
	self.portGrid.setField (self.ssh, 1, 0, (0, 0, 1, 0), anchorLeft = 1)
	self.telnet = Checkbox (_("Telnet"), todo.firewall.telnet)
	self.portGrid.setField (self.telnet, 2, 0, (0, 0, 1, 0), anchorLeft = 1)
	self.http = Checkbox (_("WWW (HTTP)"), todo.firewall.http)
	self.portGrid.setField (self.http, 0, 1, (0, 0, 1, 0), anchorLeft = 1)
	self.smtp = Checkbox (_("Mail (SMTP)"), todo.firewall.smtp)
	self.portGrid.setField (self.smtp, 1, 1, (0, 0, 1, 0), anchorLeft = 1)
	self.ftp = Checkbox (_("FTP"), todo.firewall.ftp)
	self.portGrid.setField (self.ftp, 2, 1, (0, 0, 1, 0), anchorLeft = 1)
	
	oGrid = Grid(2,1)
	oGrid.setField (Label(_("Other ports")), 0, 0, (0, 0, 1, 0), anchorLeft = 1)
	self.other = Entry (25, todo.firewall.portlist)
	oGrid.setField (self.other, 1, 0, (0, 0, 1, 0), anchorLeft = 1, growx = 1)
	bigGrid.setField (self.portGrid, 1, currentRow, (1, 0, 0, 0), anchorLeft = 1)
	bigGrid.setField (Label(""), 0, currentRow + 1, (0, 0, 0, 1), anchorLeft = 1)
	bigGrid.setField (oGrid, 1, currentRow + 1, (1, 0, 0, 1), anchorLeft = 1)
	
	self.portboxes = ( self.ssh, self.telnet, self.http, self.smtp, self.ftp,
		self.other )
		
	toplevel.add(smallGrid, 0, 1, (0, 0, 0, 0), anchorLeft = 1)
	if self.disabled.selected():
	    self.radiocb((todo, self.disabled))

	while 1:
	    result = toplevel.run ()
	    
	    rc = bb.buttonPressed (result)
	
	    if rc == "back":
		screen.popWindow()
		return INSTALL_BACK
	
	    if rc == "customize":
		
		if self.disabled.selected():
		     ButtonChoiceWindow(screen, _("Invalid Choice"),
		     _("You cannot customize a disabled firewall."),
		     buttons = [ _("OK") ], width = 40)
		else:
		    popbb = ButtonBar (screen, ((_("OK"), "ok"),))
	
		    poplevel = GridFormHelp (screen, _("Firewall Configuration - Customize"),
				"securitycustom", 1, 5)
		    text = _("You can customize your firewall in two ways. "
		    	"First, you can select to allow all traffic from "
			"certain network interfaces. Second, you can allow "
		 	"certain protocols explicitly through the firewall. "
		 	"Specify additional ports in the form 'service:protocol', "
		 	"such as 'imap:tcp'. ")
	
		    poplevel.add (TextboxReflowed(65, text), 0, 0, (0, 0, 0, 1))	 
	
		    poplevel.add (popbb, 0, 4, (0, 0, 0, 0), growx = 1)
		    poplevel.add (bigGrid, 0, 1, (0, 0, 0, 0), anchorLeft = 1)
		    

		    result2 = poplevel.run()
#                    screen.popWindow()
                    rc2 = popbb.buttonPressed(result2)


#                    rc2 = ""
                    if rc2 == "ok":

                        #- Do some sanity checking on port list
                        portstring = string.strip(self.other.value())
                        portlist = ""
                        bad_token_found = 0
                        bad_token = ""
                        if portstring != "":
                            tokens = string.split(portstring, ',')
                            for token in tokens:
                                try:
                                    if string.index(token,':'):         #- if there's a colon in the token, it's valid
                                        parts = string.split(token, ':')
                                        if len(parts) > 2:              #- We've found more than one colon.  Break loop and raise an error.
                                            bad_token_found = 1
                                            bad_token = token
                                        else:
                                            if parts[1] == 'tcp' or parts[1] == 'udp':  #-upd and tcp are the only valid protocols
                                                if portlist == "":
                                                    portlist = token
                                                else:
                                                    portlist = portlist + ',' + token
                                            else:                        #- Found a protocol other than tcp or udp.  Break loop
                                                bad_token_found = 1
                                                bad_token = token
                                                pass
                                except:
                                    if token != "":
                                        if portlist == "":
                                            portlist = token + ":tcp"
                                        else:
                                            portlist = portlist + ',' + token + ':tcp'
                                    else:
                                        pass

                        done = 0
                        if bad_token_found == 1:
                            pass
                            ButtonChoiceWindow(screen, _("Invalid Choice"),
                                               _("Warning: %s is not a valid port." %token),
                                               buttons = [ _("OK") ], width = 40)
                            screen.popWindow()
                        else:
                            todo.firewall.portlist = portlist
                            screen.popWindow()


        
#        print todo.firewall.portlist
#        import time
#        time.sleep(3)        

#                    break
	
	    if rc == "ok" or result == "F12":
                
                break
                
        screen.popWindow()

        todo.firewall.trustdevs = []
	for device in self.netCBs.keys():
	    if self.netCBs[device].selected():
		todo.firewall.trustdevs.append(device)
#	todo.firewall.portlist = self.other.value()
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
    
    def radiocb(self, args):
	(todo, widget) = args
	if widget == self.disabled:
	    todo.firewall.enabled = 0
	elif widget == self.simple:
	    todo.firewall.policy = 1
	elif widget == self.paranoid:
	    todo.firewall.policy = 0
	else:
	    raise RuntimeError, "never reached"

