from snack import *
import _balkan

class WelcomeWindow:
    def run(self, screen):
        ButtonChoiceWindow(screen, "Red Hat Linux", 
		"Welcome to Red Hat Linux!\n\n"
            "This installation process is outlined in detail in the "
	    "Official Red Hat Linux Installation Guide available from "
	    "Red Hat Software. If you have access to this manual, you "
	    "should read the installation section before continuing.\n\n"
	    "If you have purchased Official Red Hat Linux, be sure to "
	    "register your purchase through our web site, "
	    "http://www.redhat.com/.", buttons = ['Ok'])
        return 0

class PartitionWindow:
    def run(self, screen):
        device = 'hda';

	table = _balkan.readTable('/dev/' + device)
	partList = []
	for i in range(0, len(table) - 1):
	    (type, start, size) = table[i]
	    if (type == 0x83 and size):
		fullName = '/dev/%s%d' % (device, i + 1)
		partList.append((fullName, fullName))

	rc = ListboxChoiceWindow(screen, 'Root Partition',
				 'What partition would you '
				 'like to use for your root partition?',
				 partList, buttons = ['Ok', 'Back'])

	if rc[0] == 'back':
	    return -1

        return 0

class InstallInterface:

    def waitWindow(self, title, text):
	width = 40
	if (len(text) < width): width = len(text)

	t = TextboxReflowed(width, text)

	g = GridForm(self.screen, title, 1, 1)
	g.add(t, 0, 0)
	g.draw()
	self.screen.refresh()

    def popWaitWindow(self, arg):
	self.screen.popWindow()
	self.screen.refresh()

    def __init__(self):
        self.screen = SnackScreen()

    def __del__(self):
        self.screen.finish()

    def run(self, hdlist):
        steps = [
            ["Welcome", WelcomeWindow],
            ["Partition", PartitionWindow]
        ]

        step = 0
        while step >= 0 and step < len(steps) and steps[step]:

            if steps[step][1]().run(self.screen) == -1:
                step = step - 1
            else:
                step = step + 1
