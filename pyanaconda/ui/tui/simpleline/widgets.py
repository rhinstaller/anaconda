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

from pyanaconda.i18n import _
from pyanaconda.ui.tui.simpleline import base

class TextWidget(base.Widget):
    """Class to handle wrapped text output."""

    def __init__(self, text):
        """
        :param text: text to format
        :type text: unicode
        """

        base.Widget.__init__(self)
        self._text = text

    def render(self, width):
        """Renders the text widget limited to width number of columns
        (wraps to the next line when the text is longer).

        :param width: maximum width allocated to the string
        :type width: int

        :raises
        """

        base.Widget.render(self, width)
        self.write(self._text, width = width)

class CenterWidget(base.Widget):
    """Class to handle horizontal centering of content."""

    def __init__(self, w):
        """
        :param w: widget to center
        :type w: base.Widget
        """
        base.Widget.__init__(self)
        self._w = w

    def render(self, width):
        """
        Render the centered widget to internal buffer.

        :param width: maximum width the widget should use
        :type width: int
        """

        base.Widget.render(self, width)
        self._w.render(width)
        self.draw(self._w, col = (width - self._w.width) / 2)

class ColumnWidget(base.Widget):
    def __init__(self, columns, spacing = 0):
        """Create text columns

           :param columns: list containing (column width, [list of widgets to put into this column])
           :type columns: [(int, [...]), ...]

           :param spacing: number of spaces to use between columns
           :type spacing: int
           """

        base.Widget.__init__(self)
        self._spacing = spacing
        self._columns = columns

    def render(self, width):
        """Render the widget to it's internal buffer

        :param width: the maximum width the widget can use
        :type width: int

        :return: nothing
        :rtype: None
        """

        base.Widget.render(self, width)

        # the lefmost empty column
        x = 0

        # iterate over tuples (column width, column content)
        for col_width,col in self._columns:

            # set cursor to first line and leftmost empty column
            self.setxy(0, x)

            # if requested width is None, limit the maximum to width
            # and set minimum to 0
            if col_width is None:
                col_max_width = width - self.cursor[1]
                col_width = 0
            else:
                col_max_width = col_width

            # render and draw contents of column
            for item in col:
                item.render(col_max_width)
                self.draw(item, block = True)

            # recompute the leftmost empty column
            x = max((x + col_width), self.width) + self._spacing

class CheckboxWidget(base.Widget):
    """Widget to show checkbox with (un)checked box, name and description."""

    def __init__(self, key = "x", title = None, text = None, completed = None):
        """
        :param key: tick character to be used inside [ ]
        :type key: character

        :param title: the title next to the [ ] box
        :type title: unicode

        :param text: the description text to be shown on the second row in ()
        :type text: unicode

        :param completed: is the checkbox ticked or not?
        :type completed: True|False
        """

        base.Widget.__init__(self)
        self._key = key
        self._title = title
        self._text = text
        self._completed = completed

    def render(self, width):
        """Render the widget to internal buffer. It should be max width
           characters wide."""
        base.Widget.render(self, width)

        if self.completed:
            checkchar = self._key
        else:
            checkchar = " "

        # prepare the checkbox
        checkbox = TextWidget("[%s]" % checkchar)

        data = []

        # append lines
        if self.title:
            data.append(TextWidget(_(self.title)))

        if self.text:
            data.append(TextWidget("(%s)" % self.text))

        # the checkbox has two columns
        # [x] is one and is 3 chars wide
        # text is second and can occupy width - 3 - 1 (for space) chars
        cols = ColumnWidget([(3, [checkbox]), (width - 4, data)], 1)
        cols.render(width)

        # transfer the column widget rendered stuff to internal buffer
        self.draw(cols)

    @property
    def title(self):
        """Returns the first line (main title) of the checkbox."""
        return self._title

    @property
    def completed(self):
        """Returns the state of the checkbox, checked is True."""
        return self._completed

    @property
    def text(self):
        """Contains the description text from the second line."""
        return self._text

if __name__ == "__main__":
    t1 = TextWidget(u"Můj krásný dlouhý text")
    t2 = TextWidget(u"Test")
    t3 = TextWidget(u"Test 2")
    t4 = TextWidget(u"Krásný dlouhý text podruhé")
    t5 = TextWidget(u"Test 3")

    c = ColumnWidget([(15, [t1, t2, t3]), (10, [t4, t5])], spacing = 1)
    c.render(80)
    print(u"\n".join(c.get_lines()))

    print(80*"-")

    c = ColumnWidget([(20, [t1, t2, t3]), (25, [t4, t5]), (15, [t1, t2, t3])], spacing = 3)
    c.render(80)
    print(u"\n".join(c.get_lines()))
