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
    noTagTags = ('html', 'div', 'head')
    newlineTags = ('p', 'h1', 'h2', 'li')
    whiteSpaceNuker = re.compile(r"""\s+""", re.MULTILINE) 
    def __init__(self):
        self.buffer = gtk.TextBuffer(None)
        self.ignoreData = 0
        self.inList = 0
        self.currentTag = ''
        self.startOfP = 0
        HTMLParser.HTMLParser.__init__(self)
        if gtk.gdk.screen_width() >= 800:
            baseSize = 12
        else:
            baseSize = 10

        baseFont = 'sans'

        tag = self.buffer.create_tag('body')
        tag.set_property('font', '%s %d' % (baseFont, baseSize))
            
        tag = self.buffer.create_tag('p')
        tag.set_property('pixels-above-lines', '5')
        tag.set_property('pixels-below-lines', '5')

        tag = self.buffer.create_tag('tt')
        tag.set_property('font', 'Monospace %d' % (baseSize,))

        tag = self.buffer.create_tag('a')
        tag.set_property('font', '%s %d' % (baseFont, baseSize))

        tag = self.buffer.create_tag('h1')
        tag.set_property('font', '%s %d' % (baseFont, baseSize + 10))
        tag.set_property('weight', pango.WEIGHT_BOLD)        

        tag = self.buffer.create_tag('h2')
        tag.set_property('font', '%s %d' % (baseFont, baseSize + 4))
        tag.set_property('weight', pango.WEIGHT_BOLD)

        tag = self.buffer.create_tag('b')
        tag.set_property('weight', pango.WEIGHT_BOLD)

        tag = self.buffer.create_tag('i')
        tag.set_property('style', pango.STYLE_ITALIC)

        tag = self.buffer.create_tag('ul')
        tag.set_property('left-margin', 20)
        # reset spacing in paragraphs incase this list is inside <p>
        tag.set_property('pixels-above-lines', '0')
        tag.set_property('pixels-below-lines', '0')

        tag = self.buffer.create_tag('li')
        tag.set_property('indent', -9)

        self.iter = self.buffer.get_iter_at_offset(0)
        self.offsets = {}
        
    def get_buffer(self):
        return self.buffer

    def pushTag(self, tag, offset):
        if self.offsets.has_key(tag):
            self.offsets[tag].append(offset)
        else:
            self.offsets[tag] = [offset]

    def popTag(self, tag):
        if not self.offsets.has_key(tag):
            raise RuntimeError, "impossible"
        return self.offsets[tag].pop()

    # structure markup
    def handle_starttag(self, tag, attrs):
        if tag in self.ignoreTags:
            self.ignoreData += 1
            return
        self.currentTag = tag
        if tag in self.noTagTags:
            return
        self.pushTag(tag, self.iter.get_offset())
        if tag == 'li':
            self.inList += 1
            self.buffer.insert(self.iter, u'\u2022 ')
        elif tag == 'p':
            self.startOfP = 1

    def handle_endtag(self, tag):
        if tag in self.ignoreTags:
            self.ignoreData -= 1
            return
        if tag == 'li':
            self.inList -= 1
        if tag in self.noTagTags:
            return
        offset = self.popTag(tag)
        current = self.iter.get_offset()
        if tag in self.newlineTags and offset != current:
            if tag == 'p' and self.inList:
                offset -= 2
            # put a newline at the beginning
            start = self.buffer.get_iter_at_offset(offset)
            self.buffer.insert(start, '\n')
            offset += 1
            current += 1
            self.iter = self.buffer.get_iter_at_offset(current)
        start = self.buffer.get_iter_at_offset(offset)
        self.buffer.apply_tag_by_name(tag, start, self.iter)
        
    # all other markup
    def handle_data(self, data):
        if self.ignoreData == 0:
            data = data.replace('\n', ' ')
            data = self.whiteSpaceNuker.sub(' ', data)
            if self.startOfP:
                if data.startswith(' '):
                    data = data[1:]
                self.startOfP = 0
            # print '|%s|' % (data,)
            self.buffer.insert(self.iter, data)

if __name__ == '__main__':
    def quit(*args):
        gtk.main_quit()
     
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
    win.connect('destroy', quit)
    win.add(sw)
    win.show_all()
    win.set_usize(300, 300)
    gtk.main()

