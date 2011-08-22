#
# timezone_text.py: text mode timezone selection dialog
#
# Copyright (C) 2000, 2001, 2002, 2003, 2004, 2005, 2006  Red Hat, Inc.
# All rights reserved.
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

import sys
from pyanaconda import iutil
from time import *
from snack import *
from constants_text import *
from scdate.core import zonetab

from pyanaconda.constants import *
import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

sys.path.append("/usr/share/system-config-date")

class TimezoneWindow:
    def getTimezoneList(self):
        zt = zonetab.ZoneTab()
        zoneList = [ x.tz for x in zt.getEntries() ]
        zoneList.sort()
        return zoneList
        
    def currentTime(self):
	return "Current time: " + strftime("%X %Z", localtime(time()))

    def __call__(self, screen, anaconda):
	timezones = self.getTimezoneList()
	(default, asUtc) = anaconda.timezone.getTimezoneInfo()
        if not default:
	    default = anaconda.instLanguage.getDefaultTimeZone()

	bb = ButtonBar(screen, [TEXT_OK_BUTTON, TEXT_BACK_BUTTON])
	t = TextboxReflowed(30, 
			_("In which time zone are you located?"))

        if not anaconda.ksdata and not anaconda.bootloader.has_windows:
            asUtc = True

	self.l = Listbox(5, scroll = 1, returnExit = 0)

        for tz in timezones:
	    self.l.append(gettext.ldgettext("system-config-date", tz), tz)

	self.l.setCurrent(default.replace("_", " "))
        
	self.c = Checkbox(_("System clock uses UTC"), isOn = asUtc)

	self.g = GridFormHelp(screen, _("Time Zone Selection"), "timezone",
			      1, 5)
	self.g.add(t, 0, 0)
	self.g.add(self.c, 0, 2, padding = (0, 1, 0, 1), anchorLeft = 1)
	self.g.add(self.l, 0, 3, padding = (0, 0, 0, 1))
	self.g.add(bb, 0, 4, growx = 1)

        result = ""
        while True:
            result = self.g.run()
            rc = bb.buttonPressed (result)
            
            if rc == TEXT_BACK_CHECK:
                screen.popWindow()
                return INSTALL_BACK
            else:
                break

        screen.popWindow()
	anaconda.timezone.setTimezoneInfo(self.l.current().replace(" ", "_"), asUtc = self.c.selected())

	return INSTALL_OK
