from gtk import *
#import GdkImlib
import isys
import sys
import _balkan
import thread
import rpm

class WelcomeWindow:		
    def next(self, win):
        mainquit()

    def __init__(self):
        self.rc = 0

    def run(self):
        window = GtkWindow()
        window.set_border_width(10)
        window.set_title("Welcome to Red Hat Linux!")

        label = GtkLabel("Welcome to Red Hat Linux!\n\n"
	    "This installation process is outlined in detail in the "
    	    "Official Red Hat Linux Installation Guide available from "
	    "Red Hat Software. If you have access to this manual, you "
	    "should read the installation section before continuing.\n\n"
	    "If you have purchased Official Red Hat Linux, be sure to "
	    "register your purchase through our web site, "
	    "http://www.redhat.com/.")
        label.set_line_wrap (TRUE)
        buttonbox = GtkHButtonBox()
        buttonbox.set_layout(BUTTONBOX_END)
        button = GtkButton("Next >>")
        button.connect("clicked", self.next)
        buttonbox.add(button)
        vbox = GtkVBox (FALSE, 10)
        vbox.pack_start(label, TRUE, TRUE, 0)
        vbox.pack_start(buttonbox, FALSE, FALSE, 0)

        hbox = GtkHBox (FALSE, 10)

#        try:
#            im = GdkImlib.Image("shadowman-200.png")
#            im.render()
#            pix = im.make_pixmap()
#            hbox.pack_start(pix, TRUE, TRUE, 0)

#        except:
#            print "Unable to load shadowman-200.png"

        hbox.pack_start(vbox, TRUE, TRUE, 0)

        window.add(hbox)
        window.set_position(WIN_POS_CENTER)
#        window.set_default_size(640, 480)
        window.show_all()
#        mainloop()
        window.destroy()
        return self.rc

class PartitionWindow:
    def back(self, win):
        self.rc = -1
	mainquit()

    def next(self, win):
	self.rc = 0
        mainquit()

    def __init__(self):
        self.rc = 0

    def run(self, todo):
	if (not todo.setupFilesystems): return -2

        window = GtkWindow()
        window.set_border_width(10)
        window.set_title("Choose a partition")

        label = GtkLabel("What partition would you like to use for your root "
                         "partition?")
        label.set_line_wrap (TRUE)

        hbox = GtkHBox (FALSE, 10)

        device = 'hda'

        buttons = {}
        buttons[0] = None;
	numext2 = 0

        try:
    	    isys.makeDevInode(device, '/tmp/' + device)
            table = _balkan.readTable('/tmp/' + device)
    	    if len(table) - 1 > 0:
        	partbox = GtkVBox (FALSE, 5)
                for i in range(0, len(table) - 1):
                    (type, start, size) = table[i]
                    if (type == 0x83 and size):
                        buttons[numext2] = GtkRadioButton(buttons[0],
                                        '/dev/%s%d' % (device, i + 1))
                        partbox.pack_start(buttons[numext2], FALSE, FALSE, 0)
                        numext2 = numext2 + 1
            hbox.pack_start(partbox, FALSE, FALSE, 0)
            hbox.pack_start(label, FALSE, FALSE, 0)
        except:
            label = GtkLabel("Unable to read partition information")
            hbox.pack_start(label, TRUE, TRUE, 0)
            print "unable to read partitions"
 
        buttonbox = GtkHButtonBox()
        buttonbox.set_spacing(5)
        buttonbox.set_layout(BUTTONBOX_END)
        button = GtkButton("<- Back")
        button.connect("clicked", self.back)
        buttonbox.add(button)
        button = GtkButton("Next ->")
        button.connect("clicked", self.next)
        buttonbox.add(button)

        vbox = GtkVBox (FALSE, 10)
        vbox.pack_start(hbox, TRUE, TRUE, 0)
        vbox.pack_start(buttonbox, FALSE, FALSE, 0)

        window.add(vbox)
        window.set_position(WIN_POS_CENTER)
#        window.set_default_size(640, 480)
        window.show_all()
        mainloop()
	
	rootpart = ""
        for i in range(0, numext2):
            if buttons[i].active:
                rootpart = "%s%d" % (device, i + 1)

	todo.addMount(rootpart, '/')

        window.destroy()

        return self.rc


class InstallProgressWindow:
    def setPackageScale(self, amount, total):
	self.progress.update((amount * 1.0)/ total)
  	while events_pending():
	    mainiteration(FALSE)

    def completePackage(self, header):
	pass

    def setPackage(self, header):
        self.name.set_text (header[rpm.RPMTAG_NAME])
        self.size.set_text ("%d k" % (header[rpm.RPMTAG_SIZE] / 1024))
        self.summary.set_text (header[rpm.RPMTAG_SUMMARY])
        print "setPackage update"	
  	while events_pending():
	    print "   event!!"
	    mainiteration(FALSE)

    def __del__(self):
       	self.window.destroy()

    def __init__(self, total, totalSize):
        self.window = GtkWindow()
        self.window.set_border_width(10)
        self.window.set_title('Installing Packages')
        self.window.set_position(WIN_POS_CENTER)
	table = GtkTable()
	# x1, x2, y1, y2
	label = GtkLabel("Package Name:")
	label.set_alignment(1.0, 0.0)
	table.attach(label, 0, 1, 0, 1)
        label = GtkLabel("Package Size:")
	label.set_alignment(1.0, 0.0)
	table.attach(label, 0, 1, 1, 2)
        label = GtkLabel("Package Summary:")
	label.set_alignment(1.0, 0.0)
	table.attach(label, 0, 1, 2, 3, yoptions = FILL)

	self.name = GtkLabel();
	self.name.set_alignment(0, 0.0)
	self.size = GtkLabel();
	self.size.set_alignment(0, 0.0)
	self.summary = GtkLabel();
	self.summary.set_alignment(0, 0.0)
        self.summary.set_line_wrap (TRUE)
	table.attach(self.name, 1, 2, 0, 1, xoptions = FILL | EXPAND)
	table.attach(self.size, 1, 2, 1, 2, xoptions = FILL | EXPAND)
	table.attach(self.summary, 1, 2, 2, 3, xoptions = FILL | EXPAND)

	self.progress = GtkProgressBar()
	table.attach(self.progress, 0, 2, 3, 4)

	self.window.add(table)
	self.window.show_all()

class WaitWindow:
    def showWaitWindow(self, title, text):
	return
        window = GtkWindow()
        window.set_border_width(10)
        window.set_title(title)
        window.set_position(WIN_POS_CENTER)
        label = GtkLabel(text)
        label.set_line_wrap (TRUE)
	window.add(label)
	window.show_all()
	while self.lock.locked():
    	    while events_pending():
	        mainiteration(FALSE)
       	window.destroy()
        thread.exit()

    def __init__(self, title, text):
	return
	self.lock = thread.allocate_lock()
	self.lock.acquire()
	thread.start_new_thread (self.showWaitWindow, (title, text))

    def pop(self):
	return
	self.lock.release()

class InstallInterface:
    def waitWindow(self, title, text):
	return WaitWindow(title, text)

    def packageProgressWindow(self, total, totalSize):
	return InstallProgressWindow(total, totalSize)

    def run(self, todo):
        rc_parse("gtkrc")

        steps = [
            ["Welcome", WelcomeWindow, ()],
            ["Partition", PartitionWindow, (todo,)]
        ]

        step = 0
	dir = 0
        while step >= 0 and step < len(steps) and steps[step]:
            rc =  apply(steps[step][1]().run, steps[step][2])
	    if rc == -1:
		dir = -1
            else:
		dir = 1
	    step = step + dir

	todo.liloLocation("hda")
