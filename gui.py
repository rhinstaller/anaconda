#!/usr/bin/python

from gtk import *
import GdkImlib
import sys
import _balkan

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

        try:
            im = GdkImlib.Image("shadowman-200.png")
            im.render()
            pix = im.make_pixmap()
            hbox.pack_start(pix, TRUE, TRUE, 0)

        except:
            print "Unable to load shadowman-200.png"

        hbox.pack_start(vbox, TRUE, TRUE, 0)

        window.add(hbox)
        window.set_position(WIN_POS_CENTER)
#        window.set_default_size(640, 480)
        window.show_all()
        mainloop()
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

    def run(self):
        window = GtkWindow()
        window.set_border_width(10)
        window.set_title("Choose a partition")

        label = GtkLabel("What partition would you like to use for your root "
                         "partition?")
        label.set_line_wrap (TRUE)

        hbox = GtkHBox (FALSE, 10)

        device = 'hda'
        try:
            table = _balkan.readTable('/dev/' + device)
            if len(table) - 1 > 0:
                partbox = GtkVBox (FALSE, 5)
                button1 = None;
                for i in range(0, len(table) - 1):
                    (type, start, size) = table[i]
                    if (type == 0x83 and size):
                        if button1:
                            button = GtkRadioButton(button1,
                                                '/dev/%s%d' % (device, i + 1))
                            partbox.pack_start(button, FALSE, FALSE, 0)
                        else:
                            button1 = GtkRadioButton(None,
                                                 '/dev/%s%d' % (device, i + 1))
                            partbox.pack_start(button1, FALSE, FALSE, 0)
            hbox.pack_start(partbox, FALSE, FALSE, 0)
            hbox.pack_start(label, FALSE, FALSE, 0)
        except:
            label = GtkLabel("Unable to read partition information")
            hbox.pack_start(label, TRUE, TRUE, 0)
            print "unable to read partitions"

        buttonbox = GtkHButtonBox()
        buttonbox.set_spacing(5)
        buttonbox.set_layout(BUTTONBOX_END)
        button = GtkButton("<< Back")
        button.connect("clicked", self.back)
        buttonbox.add(button)
        button = GtkButton("Next >>")
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
        window.destroy()
        return self.rc

class InstallInterface:
    def waitWindow(self, title, text):
        window = GtkWindow()
        window.set_border_width(10)
        window.set_title(title)
        window.set_position(WIN_POS_CENTER)
        label = GtkLabel(text)
        label.set_line_wrap (TRUE)
	window.add(label)
	window.show_all()
	while events_pending():
	    mainiteration(TRUE)
        return window

    def popWaitWindow(self, window):
	window.destroy()

    def run(self, hdlist, rootPath):
        rc_parse("gtkrc")

        steps = [
            ["Welcome", WelcomeWindow, ()],
            ["Partition", PartitionWindow, ()]
        ]

        step = 0
        while step >= 0 and step < len(steps) and steps[step]:
            if apply(steps[step][1]().run,steps[step][2]) == -1:
                step = step - 1
            else:
                step = step + 1

