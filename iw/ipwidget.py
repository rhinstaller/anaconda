#
# class to create an IP address entry widget and to sanity check entered values
#
# Jonathan Blandford <jrb@redhat.com>
# Michael Fulbright <msf@redhat.com>
#
# Copyright 2002 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import re
import gettext
import gtk
import gobject
import gui
from translate import _, N_

ip_re = re.compile('^([0-2]?[0-9]?[0-9])\\.([0-2]?[0-9]?[0-9])\\.([0-2]?[0-9]?[0-9])\\.([0-2]?[0-9]?[0-9])$')
_=gettext.gettext

# Includes an error message, and the widget with problems
class IPError(Exception):
    pass

class IPEditor:
    def __init__ (self):
        self.entry1 = gtk.Entry(3)
        self.entry2 = gtk.Entry(3)
        self.entry3 = gtk.Entry(3)
        self.entry4 = gtk.Entry(3)
        self.entry1.set_max_length(3)
        self.entry1.connect('insert_text', self.entry_insert_text_cb, self.entry2)
        self.entry2.set_max_length(3)
        self.entry2.connect('insert_text', self.entry_insert_text_cb, self.entry3)
        self.entry3.set_max_length(3)
        self.entry3.connect('insert_text', self.entry_insert_text_cb, self.entry4)
        self.entry4.set_max_length(3)
        self.entry4.connect('insert_text', self.entry_insert_text_cb, None)

	hbox = gtk.HBox()
	hbox.pack_start(self.entry1, gtk.FALSE, gtk.FALSE)
	hbox.pack_start(gtk.Label('.'), gtk.FALSE, gtk.FALSE)
	hbox.pack_start(self.entry2, gtk.FALSE, gtk.FALSE)
	hbox.pack_start(gtk.Label('.'), gtk.FALSE, gtk.FALSE)
	hbox.pack_start(self.entry3, gtk.FALSE, gtk.FALSE)
	hbox.pack_start(gtk.Label('.'), gtk.FALSE, gtk.FALSE)
	hbox.pack_start(self.entry4, gtk.FALSE, gtk.FALSE)

	self.widget = hbox

    def getWidget(self):
	return self.widget
	
    def clear_entries (self):
        self.entry1.set_text('')
        self.entry2.set_text('')
        self.entry3.set_text('')
        self.entry4.set_text('')
        
    def hydrate (self, ip_string):
        self.clear_entries()

        #Sanity check the string
        m = ip_re.match (ip_string)
        try:
            if not m:
                return
            octets = m.groups()
            if len(octets) != 4:
                return
            for octet in octets:
                if (int(octet) < 0) or (int(octet) > 255):
                    return
        except TypeError:
            return
        self.entry1.set_text(octets[0])
        self.entry2.set_text(octets[1])
        self.entry3.set_text(octets[2])
        self.entry4.set_text(octets[3])

    def dehydrate (self):
        widget = None
        try:
            widget = self.entry1
            if int(widget.get_text()) > 255:
                raise IPError, (_("IP Addresses must contain numbers between 1 and 255"), widget)
            widget = self.entry2
            if int(widget.get_text()) > 255:
                raise IPError, (_("IP Addresses must contain numbers between 1 and 255"), widget)
            widget = self.entry3
            if int(widget.get_text()) > 255:
                raise IPError, (_("IP Addresses must contain numbers between 1 and 255"), widget)
            widget = self.entry4
            if int(widget.get_text()) > 255:
                raise IPError, (_("IP Addresses must contain numbers between 1 and 255"), widget)
        except ValueError, msg:
            raise IPError, (_("IP Addresses must contain numbers between 1 and 255"), widget)

        return self.entry1.get_text() + "." + self.entry2.get_text() + "." +self.entry3.get_text() + "." +self.entry4.get_text()

    def entry_insert_text_cb(self, entry, text, length, pos, next):
        if text == '.':
            entry.emit_stop_by_name ("insert_text")
            if next:
                next.grab_focus()
            return
        reg = re.compile ("[^0-9]+")
        if reg.match (text):
            entry.emit_stop_by_name ("insert_text")



if __name__ == "__main__":
    def output(xxx, data):
	try:
	    print data.dehydrate()
	except:
	    print "oops errors"
	gtk.mainquit()

    win = gtk.Window()
    win.connect('destroy', gtk.mainquit)
    vbox = gtk.VBox()
    ip = IPEditor()
    vbox = gtk.VBox()
    vbox.pack_start(ip.getWidget())
    button = gtk.Button("Quit")
    button.connect("pressed", output, ip)
    vbox.pack_start(button, gtk.FALSE, gtk.FALSE)
    win.add(vbox)
    win.show_all()
    gtk.mainloop()
    
