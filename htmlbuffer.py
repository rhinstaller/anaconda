#
# htmlbuffer.py - A quick hacked up HTML parser that creates a GtkTextBuffer
#                 that resembles rendered HTML.
#
# Matt Wilson <msw@redhat.com>
#
# Copyright 2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import HTMLParser
import sys
import gtk
import pango
import string
import re

class HTMLBuffer(HTMLParser.HTMLParser):
    ignoreTags = ('title',)
    noTagTags = ('html', 'body', 'div', 'head')
    newlineTags = ('p', 'h1', 'h2')
    whiteSpaceNuker = re.compile(r"""\s+""", re.MULTILINE) 
    def __init__(self):
        self.buffer = gtk.TextBuffer(None)
        self.ignoreData = 0
        self.currentTag = ''
        HTMLParser.HTMLParser.__init__(self)
        tag = self.buffer.create_tag('p')
        tag.set_property('font', 'Sans 14')
        tag = self.buffer.create_tag('tt')
        tag.set_property('font', 'Monospace 14')
        tag = self.buffer.create_tag('a')
        tag.set_property('font', 'Sans 14')
        tag = self.buffer.create_tag('h1')
        tag.set_property('font', 'Sans 24')
        tag.set_property('weight', pango.WEIGHT_BOLD)        
        tag = self.buffer.create_tag('h2')
        tag.set_property('font', 'Sans 18')
        tag.set_property('weight', pango.WEIGHT_BOLD)
        tag = self.buffer.create_tag('b')
        tag.set_property('weight', pango.WEIGHT_BOLD)
        tag = self.buffer.create_tag('i')
        tag.set_property('style', pango.STYLE_ITALIC)

        self.iter = self.buffer.get_iter_at_offset(0)
        self.offsets = [0]
        
    def get_buffer(self):
        return self.buffer
    # structure markup

    def handle_starttag(self, tag, attrs):
        if tag in self.ignoreTags:
            self.ignoreData += 1
            return
        if tag in self.newlineTags:
            self.buffer.insert(self.iter, '\n')
        if tag == 'p':
            self.buffer.insert(self.iter, '\n\t')
        self.currentTag = tag
        self.offsets.append(self.iter.get_offset())

    def handle_startendtag(self, tag, attrs):
        print (("startendtag", tag, attrs))

    def handle_endtag(self, tag):
        if tag in self.ignoreTags:
            self.ignoreData -= 1
            return
        if tag in self.noTagTags:
            return
        start = self.buffer.get_iter_at_offset(self.offsets.pop())
        self.buffer.apply_tag_by_name(tag, start, self.iter)
        
    # all other markup

    def handle_comment(self, data):
        print (("comment", data))

    def handle_charref(self, data):
        print (("charref", data))

    def handle_data(self, data):
        if self.ignoreData == 0:
            data = data.replace('\n', '')
            data = self.whiteSpaceNuker.sub(' ', data)
            if not data:
                return
            # print '|%s|' % (data,)
            self.buffer.insert(self.iter, data)

    def handle_decl(self, data):
        print (("decl", data))

    def handle_entityref(self, data):
        print (("entityref", data))

    def handle_pi(self, data):
        print (("pi", data))

    def unknown_decl(self, decl):
        print (("unknown decl", decl))

if __name__ == '__main__':
    import sys
    f = open(sys.argv[1], 'r')
    buffer = HTMLBuffer()
    buffer.feed(f.read())
    buffer.close()

    win = gtk.Window()
    view = gtk.TextView()
    view.set_buffer(buffer.get_buffer())
    view.set_property("editable", gtk.FALSE)
    view.set_property("cursor_visible", gtk.FALSE)
    view.set_wrap_mode(gtk.WRAP_WORD)
    sw = gtk.ScrolledWindow()
    sw.add(view)
    win = gtk.Window()
    win.add(sw)
    win.show_all()
    win.set_usize(300, 300)
    gtk.main()

