#!/usr/bin/python

from gtk import *
import GdkImlib
import sys

def destroy(win):
    win.destroy()
    mainquit()

def WelcomeWindow():
    window = GtkWindow()
    window.connect("destroy", destroy)
    window.set_border_width(10)
    window.set_title("Welcome to Red Hat Linux!")

    label = GtkLabel("Welcome to Red Hat Linux!\n\n"
	"This installation process is outlined in detail in the "
	"Official Red Hat Linux Installation Guide available from "
 	"Red Hat Software. If you have access to this manual, you "
	"should read the installation section before continuing.\n\n"
	"If you have purchased Official Red Hat Linux, be sure to "
	"register your purchase through our web site, "
	"http://www.redhat.com.");
    label.set_line_wrap (TRUE);
    button = GtkButton("Ok")
    button.connect("clicked", mainquit)
    vbox = GtkVBox (FALSE, 10)
    vbox.pack_start(label, FALSE, FALSE, 0)
    vbox.pack_start(button, FALSE, FALSE, 0)

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
    window.show_all()

if(__name__=="__main__"):
    for arg in sys.argv:
	if(arg=="-d"):
	    import pdb
            pdb.set_trace()

steps = {
    "Welcome Window": WelcomeWindow,
}

for step in steps.keys():
    if steps[step]:
	steps[step]()
        mainloop()
