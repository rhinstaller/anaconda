#
# pixmapRadioButtonGroup_gui.py: general purpose radio button group with pixmaps
#                                and descriptions
#
# Copyright 2000-2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import gtk
from rhpl.translate import _, N_


class pixmapRadioButtonGroup:

    def toggled (self, widget):
	if self.togglecb is not None:

	    name = None
	    for b in self.buttonToEntry.keys():
		if b == widget:
		    name = self.buttonToEntry[b]
	    
	    self.togglecb(widget, name)
	    
#        if not widget.get_active ():
#	    return

    #
    # expects a gtk pixmap for pixmap
    #
    def pixRadioButton (self, group, labelstr, pixmap, description=None):
        pix = pixmap

	hbox = gtk.HBox (gtk.FALSE, 18)
	if pix != None:
	    hbox.pack_start (pix, gtk.TRUE, gtk.TRUE, 0)

	label = gtk.Label("")
	label.set_line_wrap(gtk.TRUE)
	label.set_markup("<b>"+labelstr+"</b>")
	label.set_alignment (0.0, 0.5)
	if description is not None:
	    label.set_markup ("<b>%s</b>\n<small>%s</small>" %(labelstr,
                                                               description))
	    label.set_line_wrap(gtk.TRUE)
	    if  gtk.gdk.screen_width() > 640:
		wraplen = 350
	    else:
		wraplen = 250
		
	    label.set_size_request(wraplen, -1)
	label.set_use_markup (gtk.TRUE)
	    
	hbox.pack_start (label, gtk.TRUE, gtk.TRUE, 0)
	button = gtk.RadioButton (group)
	button.add (hbox)
        return button

    # add a entry to end of list
    def addEntry(self, name, label, pixmap=None, descr=None, userdata=None):
	node = {}
	node["name"] = name
	node["label"] = label
	node["descr"] = descr
	node["pixmap"] = pixmap
	node["userdata"] = userdata
	self.entries.append(node)

    #
    # finds entry matching name and makes it current
    #
    # MUST call AFTER calling render, since widgets are not created yet otherwise
    #
    def setCurrent(self, name):
	for b in self.buttonToEntry.keys():
	    if self.buttonToEntry[b] == name:
		b.set_active(1)

	

    #
    # returns name of current selection
    #
    # MUST call AFTER calling render, since widgets are not created yet otherwise
    #
    def getCurrent(self):
	for b in self.buttonToEntry.keys():
	    if b.get_active():
		return self.buttonToEntry[b]


    #
    # MUST call AFTER calling render, since widgets are not created yet otherwise
    #
    def packWidgetInEntry(self, name, widget):
	# find button for name
	for b in self.buttonToEntry.keys():
	    if self.buttonToEntry[b] == name:
		# now find box for button
		for (button, box, buttons) in self.topLevelButtonList:
		    if button == b:
			box.pack_end(widget)
			return

    def setToggleCallback(self, cb):
	self.togglecb = cb
	    
    # render resulting list, returns a box you can pack
    #
    # call this after adding all parents and nodes
    def render(self):

	radioGroup = None
	buttons = []
	for item in self.entries:
	    box = gtk.VBox (gtk.FALSE, 9)
	    name = item["name"]
	    label = item["label"]
	    pixmap = item["pixmap"]
	    descr = item["descr"]
	    radioGroup = self.pixRadioButton(radioGroup, _(label), pixmap,
					     description=_(descr))
	    buttons.append(radioGroup)
	    self.buttonToEntry[radioGroup] = name

	    self.topLevelButtonList.append((radioGroup, box, buttons))
	    radioGroup.connect("toggled", self.toggled)

	finalVBox = gtk.VBox(gtk.FALSE, 18)
	finalVBox.set_border_width (5)

	for (button, box, buttons) in self.topLevelButtonList:
	    vbox = gtk.VBox (gtk.FALSE, 9)
	    finalVBox.pack_start(vbox, gtk.FALSE, gtk.FALSE)
	    vbox.pack_start (button, gtk.FALSE, gtk.FALSE)
	    
	    if box:
		tmphbox = gtk.HBox(gtk.FALSE)

		crackhbox = gtk.HBox(gtk.FALSE)
		crackhbox.set_size_request(50, -1)

		tmphbox.pack_start(crackhbox, gtk.FALSE, gtk.FALSE)
		tmphbox.pack_start(box, gtk.TRUE, gtk.TRUE)
		vbox.pack_start(tmphbox, gtk.FALSE, gtk.FALSE)
		
        return finalVBox
    
    
    # InstallPathWindow tag="instpath"
    def __init__(self):
	self.entries = []
	self.topLevelButtonList = []
	self.buttonToEntry = {}
	self.togglecb = None


if __name__ == "__main__":
    def readPixmap(fn):
	pixbuf = gtk.gdk.pixbuf_new_from_file(fn)

	source = gtk.IconSource()
	source.set_pixbuf(pixbuf)
	source.set_size(gtk.ICON_SIZE_DIALOG)
	source.set_size_wildcarded(gtk.FALSE)
	iconset = gtk.IconSet()
	iconset.add_source(source)
	p = gtk.image_new_from_icon_set(iconset, gtk.ICON_SIZE_DIALOG)

	return p

    def nowquit(widget):
	global r

	print "selection -> ",r.getCurrent()

	gtk.mainquit()
	
    win = gtk.Window()
    win.connect('destroy', nowquit)


    if 0:
	opts = ['Red Hat 8.0 - /dev/hda1', 'Red Hat 7.1 - /dev/hda5']
    else:
	opts = ['Red Hat 8.0 - /dev/hda1']

    label = _("The following Red Hat product will be upgraded:")
    upgradeoption = gtk.OptionMenu()
    upgradeoptionmenu = gtk.Menu()
    for lev in opts:
	item = gtk.MenuItem(lev)
	item.show()        
	upgradeoptionmenu.add(item)

    upboxtmp = gtk.VBox(gtk.FALSE, 5)
    l = gtk.Label(label)
    l.set_alignment(0.0, 0.0)
    upboxtmp.pack_start(l)
    upboxtmp.pack_start(upgradeoption)
    upgradeoption.set_menu(upgradeoptionmenu)

    upgradeoption.set_sensitive(0)
    
    # hack indent it
    upbox = gtk.HBox(gtk.FALSE)

    crackhbox = gtk.HBox(gtk.FALSE)
    crackhbox.set_size_request(80, -1)

    upbox.pack_start(crackhbox, gtk.FALSE, gtk.FALSE)
    upbox.pack_start(upboxtmp, gtk.TRUE, gtk.TRUE)

    r = pixmapRadioButtonGroup()
    r.addEntry("Upgrade Existing Installation", pixmap=readPixmap("/usr/share/anaconda/pixmaps/upgrade.png"),  descr="Choose this option if you would like to upgrade your existing Red Hat Linux system.  This option will preserve the data on your driver.", userdata="data")

    r.addEntry("Reinstall Red Hat Linux", pixmap=readPixmap("../pixmaps/install.png"),
	       descr="Choose this option to reinstall your system.  Depending on how you partition your system your previous data may or may not be lost.", userdata="data2")
    b = r.render()
    r.setCurrent("Don't Upgrade")

    r.packWidgetInEntry("Upgrade Existing Installation", upbox)

    vbox = gtk.VBox()
    vbox.pack_start(b, gtk.FALSE, gtk.FALSE)
    
    button = gtk.Button("Quit")
    button.connect("pressed", nowquit)
    vbox.pack_start(button, gtk.FALSE, gtk.FALSE)
    
    win.add(vbox)
    win.show_all()
    gtk.mainloop()

    
    
