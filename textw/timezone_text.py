import string
import iutil
import os
from time import *
from snack import *
from constants_text import *
from translate import _

class TimezoneWindow:

    def getTimezoneList(self, test):
	if not os.access("/usr/lib/timezones.gz", os.R_OK):
            if test:
                cmd = "./gettzlist"
                stdin = None
            else:
                zoneList = iutil.findtz('/usr/share/zoneinfo', '')
                cmd = ""
                stdin = None
	else:
	    cmd = "/usr/bin/gunzip"
	    stdin = os.open("/usr/lib/timezones.gz", 0)

        if cmd != "":
            zones = iutil.execWithCapture(cmd, [ cmd ], stdin = stdin)
            zoneList = string.split(zones)

	if (stdin != None):
            os.close(stdin)

	return zoneList

    def updateSysClock(self):
	if os.access("/sbin/hwclock", os.X_OK):
	    args = [ "/sbin/hwclock" ]
	else:
	    args = [ "/usr/sbin/hwclock" ]

	args.append("--hctosys")
	if self.c.selected():
	    args.append("--utc")

	iutil.execWithRedirect(args[0], args)
	self.g.setTimer(500)
	self.updateClock()

    def updateClock(self):
        # disable for now
        return
        
	if os.access("/usr/share/zoneinfo/" + self.l.current(), os.R_OK):
	    os.environ['TZ'] = self.l.current()
	    self.label.setText(self.currentTime())
	else:
	    self.label.setText("")

    def currentTime(self):
	return "Current time: " + strftime("%X %Z", localtime(time()))

    def __call__(self, screen, todo, test):
	timezones = self.getTimezoneList(test)
	rc = todo.getTimezoneInfo()
	if rc:
	    (default, asUtc, asArc) = rc
	else:
	    default = iutil.defaultZone()
	    asUtc = 0

	bb = ButtonBar(screen, [(_("OK"), "ok"), (_("Back"), "back")])
	t = TextboxReflowed(30, 
			_("What time zone are you located in?"))

#
# disabling this for now
# 
#	self.label = Label(self.currentTime())
		
	self.l = Listbox(5, scroll = 1, returnExit = 0)

        for tz in timezones:
	    self.l.append(tz, tz)

	self.l.setCurrent(default)
#	self.l.setCallback(self.updateClock)

	self.c = Checkbox(_("Hardware clock set to GMT?"), isOn = asUtc)
#	self.c.setCallback(self.updateSysClock)

	self.g = GridFormHelp(screen, _("Time Zone Selection"), "timezone",
			      1, 5)
	self.g.add(t, 0, 0)
#	self.g.add(self.label, 0, 1, padding = (0, 1, 0, 0), anchorLeft = 1)
	self.g.add(self.c, 0, 2, padding = (0, 1, 0, 1), anchorLeft = 1)
	self.g.add(self.l, 0, 3, padding = (0, 0, 0, 1))
	self.g.add(bb, 0, 4, growx = 1)

# disabling for now
#	self.updateClock()
#	self.updateSysClock()
#
#	self.g.setTimer(500)
#
#	result = "TIMER"
#	while result == "TIMER":
#	    result = self.g.run()
#	    if result == "TIMER":
#		self.updateClock()

        result = ""
        while 1:
            result = self.g.run()
            rc = bb.buttonPressed (result)
            
            if rc == "back":
                screen.popWindow()
                return INSTALL_BACK
            else:
                break

        screen.popWindow()
	todo.setTimezoneInfo(self.l.current(), asUtc = self.c.selected())

	return INSTALL_OK


