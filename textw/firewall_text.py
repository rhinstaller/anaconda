#
# firewall_text.py: text mode firewall setup
#
# Bill Nottingham <notting@redhat.com>
#
# Copyright 2001-2003 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

from snack import *
from constants_text import *
from rhpl.translate import _

class FirewallWindow:
    def __call__(self, screen, intf, network, firewall, security):
        self.intf = intf
	
	bb = ButtonBar (screen, (TEXT_OK_BUTTON, (_("Customize"), "customize"), TEXT_BACK_BUTTON))
	
	toplevel = GridFormHelp (screen, _("Firewall"),
				"securitylevel", 1, 5)
	text = _("A firewall can help prevent unauthorized access to your "
                 "computer from the outside world.  Would you like to enable "
                 "a firewall?")
	toplevel.add (TextboxReflowed(50, text), 0, 0, (0, 0, 0, 1))	 
						
	toplevel.add (bb, 0, 4, (0, 0, 0, 0), growx = 1)
	
	smallGrid = Grid(2,1)
	
	bigGrid = Grid(2,15)
	
	typeGrid = Grid(2,1)

# 	label = Label(_("Security Level:"))
# 	smallGrid.setField (label, 0, 0, (0, 0, 0, 1), anchorLeft = 1)
	
	
	self.enabled = SingleRadioButton(_("Enable firewall"), None, firewall.enabled)
	self.enabled.setCallback(self.radiocb, (firewall, self.enabled))
	typeGrid.setField (self.enabled, 0, 0, (0, 0, 1, 0), anchorLeft = 1)
	self.disabled = SingleRadioButton(_("No firewall"), self.enabled, not firewall.enabled)
	self.disabled.setCallback(self.radiocb, (firewall, self.disabled))
	typeGrid.setField (self.disabled, 1, 0 , (0, 0, 1, 0), anchorRight = 1)
	
	smallGrid.setField (typeGrid, 0, 0, (1, 0, 0, 1), anchorLeft = 1, growx = 1)
	
	currentRow = 1
	devices = network.available().keys()

	if (devices):
	    devices.sort()
	    cols = len(devices)
	    if cols > 4:
		rows = cols % 4
		cols = 4
	    else:
		rows = 1
		
            if devices != []:
                bigGrid.setField (Label(_("Trusted Devices:")), 0,
				  currentRow, (0, 0, 0, 1), anchorLeft = 1)

		devicelist = CheckboxTree(height=3, scroll=1)
                bigGrid.setField (devicelist, 1, currentRow,
				  (1, 0, 0, 1), anchorLeft = 1)
		currentRow = currentRow + 1
		for dev in devices:
                    devicelist.append(dev, selected = (dev in firewall.trustdevs))
		    
	bigGrid.setField (Label(_("Allow incoming:")), 0, currentRow, (0, 0, 0, 0),
		anchorTop = 1)
	    
	self.portGrid = Grid(3,2)
	    
	self.ssh = Checkbox (_("SSH"), firewall.ssh)
	self.portGrid.setField (self.ssh, 1, 0, (0, 0, 1, 0), anchorLeft = 1)
	self.telnet = Checkbox (_("Telnet"), firewall.telnet)
	self.portGrid.setField (self.telnet, 2, 0, (0, 0, 1, 0), anchorLeft = 1)
	self.http = Checkbox (_("WWW (HTTP)"), firewall.http)
	self.portGrid.setField (self.http, 0, 1, (0, 0, 1, 0), anchorLeft = 1)
	self.smtp = Checkbox (_("Mail (SMTP)"), firewall.smtp)
	self.portGrid.setField (self.smtp, 1, 1, (0, 0, 1, 0), anchorLeft = 1)
	self.ftp = Checkbox (_("FTP"), firewall.ftp)
	self.portGrid.setField (self.ftp, 2, 1, (0, 0, 1, 0), anchorLeft = 1)
	
	oGrid = Grid(2,1)
	oGrid.setField (Label(_("Other ports")), 0, 0, (0, 0, 1, 0), anchorLeft = 1)
	self.other = Entry (25, firewall.portlist)
	oGrid.setField (self.other, 1, 0, (0, 0, 1, 0), anchorLeft = 1, growx = 1)
	bigGrid.setField (self.portGrid, 1, currentRow, (1, 0, 0, 0), anchorLeft = 1)
	bigGrid.setField (Label(""), 0, currentRow + 1, (0, 0, 0, 1), anchorLeft = 1)
	bigGrid.setField (oGrid, 1, currentRow + 1, (1, 0, 0, 1), anchorLeft = 1)
	
	self.portboxes = ( self.ssh, self.telnet, self.http, self.smtp, self.ftp,
		self.other )
		
	toplevel.add(smallGrid, 0, 1, (0, 0, 0, 0), anchorLeft = 1)
	if self.disabled.selected():
	    self.radiocb((firewall, self.disabled))

	while 1:
	    result = toplevel.run ()
	    
	    rc = bb.buttonPressed (result)
	
	    if rc == TEXT_BACK_CHECK:
		screen.popWindow()
		return INSTALL_BACK
	
	    if rc == "customize":
		
		if self.disabled.selected():
		     ButtonChoiceWindow(screen, _("Invalid Choice"),
		     _("You cannot customize a disabled firewall."),
		     buttons = [ TEXT_OK_STR ], width = 40)
		else:
		    popbb = ButtonBar (screen, (TEXT_OK_BUTTON,))
	
		    poplevel = GridFormHelp (screen, _("Firewall Configuration - Customize"),
				"securitycustom", 1, 5)
		    text = _("You can customize your firewall in two ways. "
		    	"First, you can select to allow all traffic from "
			"certain network interfaces. Second, you can allow "
		 	"certain protocols explicitly through the firewall. "
		 	"In a comma separated list, specify additional ports in the form "
                        "'service:protocol' such as 'imap:tcp'. ")
	
		    poplevel.add (TextboxReflowed(65, text), 0, 0, (0, 0, 0, 1))	 
	
		    poplevel.add (popbb, 0, 4, (0, 0, 0, 0), growx = 1)
		    poplevel.add (bigGrid, 0, 1, (0, 0, 0, 0), anchorLeft = 1)
		    

		    result2 = poplevel.run()
#                    screen.popWindow()
                    rc2 = popbb.buttonPressed(result2)


#                    rc2 = ""
                    if rc2 == TEXT_OK_CHECK or result2 == TEXT_F12_CHECK:

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

                        if bad_token_found == 1:
                            self.intf.messageWindow(_("Invalid Choice"),
                                                    _("Warning: %s is not a "
                                                      "valid port.") %(token,))
                            screen.popWindow()
                        else:
                            firewall.portlist = portlist
                            screen.popWindow()
	
	    if rc == TEXT_OK_CHECK or result == TEXT_F12_CHECK:
		if self.disabled.selected():
		    rc2 = self.intf.messageWindow(_("Warning - No Firewall"),
		   _("If this system is attached directly to the Internet or "
		     "is on a large public network, it is recommended that a "
		     "firewall be configured to help prevent unauthorized "
		     "access.  However, you have selected not to "
		     "configure a firewall.  Choose \"Proceed\" to continue "
		     "without a firewall."),
		      type="custom", custom_icon="warning",
		      custom_buttons=[_("_Back"), _("_Proceed")])
		    
		    if rc2 == 0:
			continue
		    else:
			break
		else:
		    break
                
        screen.popWindow()

        firewall.trustdevs = []
        if devices != []:
            for dev in devicelist.getSelection():
                firewall.trustdevs.append(dev)

#	firewall.portlist = self.other.value()
	firewall.ssh = self.ssh.selected()
	firewall.telnet = self.telnet.selected()
	firewall.http = self.http.selected()
	firewall.smtp = self.smtp.selected()
	firewall.ftp = self.ftp.selected()
	if self.disabled.selected():
	    firewall.enabled = 0
	else:
	    firewall.enabled = 1

	return INSTALL_OK
    
    def radiocb(self, args):
	(firewall, widget) = args
	if widget == self.disabled:
	    firewall.enabled = 0
	elif widget == self.enabled:
	    firewall.enabled = 1
	else:
	    raise RuntimeError, "never reached"

