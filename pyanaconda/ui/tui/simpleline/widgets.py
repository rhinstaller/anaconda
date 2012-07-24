# encoding: utf-8
#
# Widgets for Anaconda TUI.
#
# Copyright (C) 2012  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
# Red Hat Author(s): Martin Sivak <msivak@redhat.com>
#

__all__ = ["TextWidget", "ColumnWidget", "CheckboxWidget", "CenterWidget"]

import base

class TextWidget(base.Widget):
    def __init__(self, text):
        base.Widget.__init__(self)
        self._text = text

    def render(self, width):
        self.clear()
        self.write(self._text, width = width)

class CenterWidget(base.Widget):
    def __init__(self, w):
        base.Widget.__init__(self)
        self._w = w

    def render(self, width):
        self.clear()
        self._w.render(width)
        self.draw(self._w, col = (width - self._w.width) / 2)

class ColumnWidget(base.Widget):
    def __init__(self, columns, spacing = 0):
        """Create text columns

           @param columns list containing (column width, [list of widgets to put into this column])
           @type columns [(int, [...]), ...]

           @param spacing number of spaces to use between columns
           @type int
           """

        base.Widget.__init__(self)
        self._spacing = spacing
        self._columns = columns

    def render(self, width):
        self.clear()

        x = 0
        for col_width,col in self._columns:
            self.setxy(0, x)

            if col_width is None:
                col_max_width = width - self.cursor[1]
                col_width = 0
            else:
                col_max_width = col_width

            for item in col:
                item.render(col_max_width)
                self.draw(item, block = True)

            x = max((x + col_width), self.width) + self._spacing

class CheckboxWidget(base.Widget):
    def __init__(self, key = None, title = None, text = None, completed = None):
        base.Widget.__init__(self)
        self._key = key
        self._title = title
        self._text = text
        self._completed = completed

    def render(self, width):
        self.clear()

        if self.completed:
            checkchar = "x"
        else:
            checkchar = " "

        checkbox = TextWidget("[%s]" % checkchar)

        data = []

        if self.title:
            data.append(TextWidget(self.title))

        if self.text:
            data.append(TextWidget("(%s)" % self.text))

        cols = ColumnWidget([(3, [checkbox]), (width - 4, data)], 1)
        cols.render(width)
        self.draw(cols)

    @property
    def title(self):
        return self._title

    @property
    def completed(self):
        return self._completed

    @property
    def text(self):
        return self._text

if __name__ == "__main__":
    t1 = TextWidget(u"Můj krásný dlouhý text")
    t2 = TextWidget(u"Test")
    t3 = TextWidget(u"Test 2")
    t4 = TextWidget(u"Krásný dlouhý text podruhé")
    t5 = TextWidget(u"Test 3")

    c = ColumnWidget([(15, [t1, t2, t3]), (10, [t4, t5])], spacing = 1)
    c.render(80)
    print unicode(c)

    print 80*"-"

    c = ColumnWidget([(20, [t1, t2, t3]), (25, [t4, t5]), (15, [t1, t2, t3])], spacing = 3)
    c.render(80)
    print unicode(c)
