#
# firewall_text.py: text mode firewall setup
#
# Bill Nottingham <notting@redhat.com>
# Jeremy Katz <katzj@redhat.com>
#
# Copyright 2001-2004 Red Hat, Inc.
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
from rhpl.log import log
from flags import flags

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

	self.enabled = SingleRadioButton(_("Enable firewall"), None, firewall.enabled)
	self.enabled.setCallback(self.radiocb, (firewall, self.enabled))
	typeGrid.setField (self.enabled, 0, 0, (0, 0, 1, 0), anchorLeft = 1)
	self.disabled = SingleRadioButton(_("No firewall"), self.enabled, not firewall.enabled)
	self.disabled.setCallback(self.radiocb, (firewall, self.disabled))
	typeGrid.setField (self.disabled, 1, 0 , (0, 0, 1, 0), anchorRight = 1)
	
	smallGrid.setField (typeGrid, 0, 0, (1, 0, 0, 1), anchorLeft = 1, growx = 1)
	
	currentRow = 1
	bigGrid.setField (Label(_("Allow incoming:")), 0, currentRow, (0, 0, 0, 0),
		anchorTop = 1)
	    
	self.portGrid = Grid(1, len(firewall.services))
        # list of Service, Checkbox tuples
        self.portboxes = []
        count = 0
        for serv in firewall.services:
            s = Checkbox(_(serv.get_name()), serv.get_enabled())
            self.portboxes.append((serv, s))
            self.portGrid.setField (s, 0, count, (0, 0, 1, 0), anchorLeft = 1)
            count += 1
	
	bigGrid.setField (self.portGrid, 1, currentRow, (1, 0, 0, 0), anchorLeft = 1)
	bigGrid.setField (Label(""), 0, currentRow + 1, (0, 0, 0, 1), anchorLeft = 1)
	
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
	
		    poplevel = GridFormHelp (screen, _("Customize Firewall Configuration"),
				"securitycustom", 1, 5)
		    text = _("With a firewall, you may wish to allow access "
                             "to specific services on your computer from "
                             "others.  Allow access to which services?")
	
		    poplevel.add (TextboxReflowed(65, text), 0, 0, (0, 0, 0, 1))	 
	
		    poplevel.add (popbb, 0, 4, (0, 0, 0, 0), growx = 1)
		    poplevel.add (bigGrid, 0, 1, (0, 0, 0, 0), anchorLeft = 1)
		    

		    result2 = poplevel.run()
                    rc2 = popbb.buttonPressed(result2)

                    if rc2 == TEXT_OK_CHECK or result2 == TEXT_F12_CHECK:
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

        for (s, cb) in self.portboxes:
            s.set_enabled(cb.selected())
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



class SELinuxWindow:
    def __call__(self, screen, intf, network, firewall, security):
        if flags.selinux == 0:
            log("selinux disabled, not showing selinux config screen")
            return INSTALL_NOOP
        
        self.intf = intf

        toplevel = GridFormHelp (screen, _("Security Enhanced Linux"),
                                 "selinux", 1, 5)
        text = _("Security Enhanced Linux (SELinux) provides stricter access "
                 "controls to improve the security of your system.  How would "
                 "you like this support enabled?")

        toplevel.add(TextboxReflowed(50, text), 0, 0, (0,0,0,1))


        grid = Grid(3, 1)
	disable = SingleRadioButton(_("Disable SELinux"), None, (security.getSELinux() == 0))
        toplevel.add(disable, 0, 1, (0,0,0,0))
	warn = SingleRadioButton(_("Warn on violations"), disable, (security.getSELinux() == 1))
        toplevel.add(warn, 0, 2, (0,0,0,0))
	enable = SingleRadioButton(_("Active"), warn, (security.getSELinux() == 2))
        toplevel.add(enable, 0, 3, (0,0,0,1))

        bb = ButtonBar (screen, (TEXT_OK_BUTTON, TEXT_BACK_BUTTON))
        toplevel.add(bb, 0, 4, (0, 0, 0, 0), growx = 1)

        while 1:
            result = toplevel.run()

            rc = bb.buttonPressed (result)

            if rc == TEXT_BACK_CHECK:
                screen.popWindow()
                return INSTALL_BACK

            break

        if enable.selected():
            security.setSELinux(2)
        elif warn.selected():
            security.setSELinux(1)
        elif disable.selected():
            security.setSELinux(0)
            
        screen.popWindow()
        return INSTALL_OK

