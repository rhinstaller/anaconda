import _balkan
from snack import *
import _snack

class WelcomeWindow:
    def run(self, screen):
        _snack.message("Red Hat Linux", "Welcome to Red Hat Linux!\n\n"
            "This installation process is outlined in detail in the "
	    "Official Red Hat Linux Installation Guide available from "
	    "Red Hat Software. If you have access to this manual, you "
	    "should read the installation section before continuing.\n\n"
	    "If you have purchased Official Red Hat Linux, be sure to "
	    "register your purchase through our web site, "
	    "http://www.redhat.com/.")
        return 0

class PartitionWindow:
    def run(self, screen):
        device = 'hda';
	try:
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

            print rc
	    if rc[0] == 'back':
                return -1
        except IOError:
            print "unable to read partition table"

        return 0

class InstallInterface:

    def run(self):
        screen = SnackScreen()
  
        steps = [
            ["Welcome", WelcomeWindow],
            ["Partition", PartitionWindow]
        ]

        step = 0
        while step >= 0 and step < len(steps) and steps[step]:

            if steps[step][1]().run(screen) == -1:
                step = step - 1
            else:
                step = step + 1

        screen.finish()