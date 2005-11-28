#!/usr/bin/python
#
# release_notes_viewer_iw.py - viewer for release notes
#
# Michael Fulbright <msf@redhat.com>
#
# Copyright 2003 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import sys
import os
import gtk
import re

from rhpl.translate import _, N_

sys.path.append('/usr/lib/anaconda')

from gui import TextViewBrowser, addFrame
import gtkhtml2

screenshot = None

htmlheader = "<html><head><meta http-equiv=\"Content-Type\" content=\"text/html; charset=utf-8\"></head><body bgcolor=\"white\">"
htmlfooter = "</body></html>"

def loadReleaseNotes(fn):
    doc = gtkhtml2.Document()
    doc.clear()
    doc.open_stream("text/html")
    
    if os.access(fn, os.R_OK):
	file = open(fn, "r")
	if fn.endswith('.html'):
            doc.write_stream(file.read())            
	else:
            # this is a minimal attempt to clean up a UTF-8 text file for displayment
            # in the gtkhtml2 widget.  it isn't perfect, nor should anyone care that
            # much.  as long as it displays the release notes reasonably well.

            # the next X number of lines of code can crank out the HTML to a temp
            # file if you set this variable to 1
            drn = 1
            #drn = 0

            if drn == 1:
                debugfile = open("/tmp/relnotes-debug.html", "w")
                debugfile.write(htmlheader)

            doc.write_stream(htmlheader)

            tok = file.readline()
            doc.write_stream("<p>")

            if drn == 1:
                debugfile.write("<p>")

            while tok:
                if tok == "\n":
                   if drn == 1:
                       debugfile.write("</p>")
                   doc.write_stream("</p>")

                if drn == 1:
                    debugfile.write(tok)
                doc.write_stream(tok)

                if tok == "\n":
                   if drn == 1:
                       debugfile.write("<p>")
                   doc.write_stream("<p>")

                tok = file.readline()

            if drn == 1:
                debugfile.write(htmlfooter)
                debugfile.close()

            doc.write_stream(htmlfooter)
        doc.close_stream()
        file.close()
    else:
        doc.write_stream(htmlheader)        
        doc.write_stream(_("Release notes are missing.\n"))
        doc.write_stream(htmlfooter)
        
    view = gtkhtml2.View()
    view.set_document(doc)
    return view

def relnotes_closed(widget, data):
    os._exit(0)


def exposeCB(widget, event, data):
    global screenshot
    
    width = gtk.gdk.screen_width()
    height = gtk.gdk.screen_height()
    gc = gtk.gdk.GC(widget.window)
    screenshot.render_to_drawable(widget.window,
				  gc,
				  0, 0,
				  0, 0,
				  width, height,
				  gtk.gdk.RGB_DITHER_NONE,
				  0, 0)

#
# MAIN
#
if __name__ == "__main__":

    take_screenshot = 0

    #
    # cover up background with screenshot so they cant do anything to it
    #

    if take_screenshot:
	width = gtk.gdk.screen_width()
	height = gtk.gdk.screen_height()
	screenshot = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, False, 8,
					width, height)

	screenshot.get_from_drawable(gtk.gdk.get_default_root_window(),
					 gtk.gdk.colormap_get_system(),
					 0, 0, 0, 0,
					 width, height)

	screenshot.save ("testimage", "png")

	win = gtk.Window(gtk.WINDOW_TOPLEVEL)

	area = gtk.DrawingArea()
	area.set_size_request(width, height)
	area.connect("expose-event", exposeCB, None)

	win.add(area)
	win.show_all()

    #
    # now do release notes dialog
    #
    
    textWin = gtk.Dialog(flags=gtk.DIALOG_MODAL)

    table = gtk.Table(3, 3, False)
    textWin.vbox.pack_start(table)
    textWin.add_button('gtk-close', gtk.RESPONSE_NONE)
    textWin.connect("response", relnotes_closed)
    vbox1 = gtk.VBox ()        
    vbox1.set_border_width (10)
    frame = gtk.Frame ("")
    frame.add(vbox1)
    frame.set_label_align (0.5, 0.5)
    frame.set_shadow_type (gtk.SHADOW_NONE)

    textWin.set_position (gtk.WIN_POS_CENTER)

    relnotes = loadReleaseNotes(sys.argv[1])

    if relnotes is not None:
	sw = gtk.ScrolledWindow()
	sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_ALWAYS)
	sw.set_shadow_type(gtk.SHADOW_IN)
	sw.add(relnotes)
	vbox1.pack_start(sw)

	a = gtk.Alignment (0, 0, 1.0, 1.0)
	a.add (frame)

	#textWin.set_default_size (635, 393)
	#textWin.set_size_request (635, 393)

	if gtk.gdk.screen_width() >= 800:
		rn_w = 800
		rn_h = 600
	else:
		rn_w = 640
		rn_h = 480

	textWin.set_default_size (rn_w, rn_h)
	textWin.set_size_request (rn_w, rn_h)
	textWin.set_position (gtk.WIN_POS_CENTER)

	table.attach (a, 1, 2, 1, 2,
		      gtk.FILL | gtk.EXPAND,
		      gtk.FILL | gtk.EXPAND, 5, 5)

	textWin.set_border_width(0)
	addFrame(textWin, _("Release Notes"))
	textWin.show_all()
    else:
	textWin.set_position (gtk.WIN_POS_CENTER)
	label = gtk.Label(_("Unable to load file!"))

	table.attach (label, 1, 2, 1, 2,
		      gtk.FILL | gtk.EXPAND, gtk.FILL | gtk.EXPAND, 5, 5)

	textWin.set_border_width(0)
	addFrame(textWin)
	textWin.show_all()

    # set cursor to normal (assuming that anaconda set it to busy when
    # it exec'd this viewer app to give progress indicator to user).
    root = gtk.gdk.get_default_root_window()
    cursor = gtk.gdk.Cursor(gtk.gdk.LEFT_PTR)
    root.set_cursor(cursor)

    gtk.main()
    
