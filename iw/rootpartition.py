from gtk import *
from iw import *
import isys
import _balkan

class PartitionWindow (InstallWindow):

    def __init__ (self, ics):
	InstallWindow.__init__ (self, ics)

        self.todo = ics.getToDo ()
        ics.setTitle ("Root Partition Selection")
        ics.setHTML ("<HTML><BODY>Select a root partition"
                     "</BODY></HTML>")
	ics.setNextEnabled (TRUE)

    def getNext (self):
        for i in self.buttons.keys ():
            if self.buttons[i].active:
                rootpart = "%s%d" % (self.device, i + 1)
                
        self.todo.addMount(rootpart, '/')
        return None

    def getScreen (self):
        label = GtkLabel("What partition would you like to use for your root "
                         "partition?")
        label.set_line_wrap (TRUE)

        hbox = GtkVBox (FALSE, 10)

        self.device = 'hda'

        self.buttons = {}
        self.buttons[0] = None
	numext2 = 0

        try:
    	    isys.makeDevInode(self.device, '/tmp/' + self.device)
            table = _balkan.readTable('/tmp/' + self.device)
    	    if len(table) - 1 > 0:
        	partbox = GtkVBox (FALSE, 5)
                for i in range(0, len(table) - 1):
                    (type, start, size) = table[i]
                    if (type == 0x83 and size):
                        button = GtkRadioButton(self.buttons[0],
                                                '/dev/%s%d' % (self.device, i + 1))
                        self.buttons[i] = button
                        partbox.pack_start(button, FALSE, FALSE, 0)
            hbox.pack_start(label, FALSE, FALSE, 0)
            hbox.pack_start(partbox, FALSE, FALSE, 0)
        except:
            label = GtkLabel("Unable to read partition information")
            hbox.pack_start(label, TRUE, TRUE, 0)
            print "unable to read partitions"
 
        return hbox
