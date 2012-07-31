# Base classes for the Anaconda TUI framework.
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

__all__ = ["ExitMainLoop", "App", "UIScreen", "Widget"]

import readline

class ExitAllMainLoops(Exception):
    pass

class ExitMainLoop(Exception):
    pass


class App(object):
    def __init__(self, title, yes_or_no_question = None, width = 80):
        self._header = title
        self._spacer = "\n".join(2*[width*"="])
        self._width = width
        self.quit_question = yes_or_no_question

        # screen stack contains triplets
        #  UIScreen to show
        #  arguments for it's show method
        #  value indicating whether new mainloop is needed - None = do nothing, True = execute, False = already running, exit when window closes
        self._screens = []

    def switch_screen(self, ui, args = None):
        """Schedules a screen to replace the current one."""
        oldscr, oldattr, oldloop = self._screens.pop()
        self._screens.append((ui, args, oldloop))
        self.redraw()

    def switch_screen_with_return(self, ui, args = None):
        """Schedules a screen to show, but keeps the current one in stack to return to, when the new one is closed."""
        self._screens.append((ui, args, None))
        self.redraw()

    def switch_screen_modal(self, ui, args = None):
        """Starts a new screen right away, so the caller can collect data back. When the new screen is closed, the caller is redisplayed."""
        self._screens.append((ui, args, True))
        self._do_redraw()

    def schedule_screen(self, ui, args = None):
        """Add screen to the bottom of the stack."""
        self._screens.insert(0, (ui, args, None))

    def close_screen(self, scr = None):
        oldscr, oldattr, oldloop = self._screens.pop()
        if scr is not None:
            assert oldscr == scr

        # we are in modal window, end it's loop
        assert oldloop != True # this cannot happen, if we are closing the window, the loop must be running or not there
        if oldloop == False:
            raise ExitMainLoop()

        if self._screens:
            self.redraw()
        else:
            raise ExitMainLoop()

    def _do_redraw(self):
        """Draws the current screen and returns True if user input is requested.
           If modal screen is requested, starts a new loop and initiates redraw after it ends."""
        if not self._screens:
            raise ExitMainLoop()

        screen, args, newloop = self._screens[-1]

        if newloop == True:
            self._screens.pop()
            self._screens.append((screen, args, False))
            self.mainloop()
            self.redraw()
            input_needed = False # we have to skip input once, to redisplay the screen first
        else:
            input_needed = screen.refresh(args)
            screen.window.show_all()
            self._redraw = False

        return input_needed

    def run(self):
        try:
            self.mainloop()
        except ExitAllMainLoops:
            pass

    def mainloop(self):
        self._redraw = True
        last_screen = None
        error_counter = 0
        while self._screens:
            if self._redraw:
                print self._spacer

            try:
                if self._redraw or last_screen != self._screens[-1]:
                    if not self._do_redraw():
                        continue

                last_screen = self._screens[-1][0]

                prompt = last_screen.prompt()
                if prompt is None:
                    self.redraw()
                    continue

                c = raw_input(prompt)

                if not self.input(c):
                    error_counter += 1

                if error_counter >= 5:
                    self.redraw()

                if self._redraw:
                    error_counter = 0
            except ExitMainLoop:
                break
            except ExitAllMainLoops:
                raise

    def input(self, key):
        """Method called to process unhandled input key presses."""
        if self._screens:
            key = self._screens[-1][0].input(key)
            if key is None:
                return True

        if self._screens and (key == 'c'):
            self.close_screen()
            return True

        elif self._screens and (key == 'q'):
            if self.quit_question:
                d = self.quit_question(self, u"Do you really want to quit?")
                self.switch_screen_modal(d)
                if d.answer:
                    raise ExitAllMainLoops()
            return True

        return False

    def redraw(self):
        self._redraw = True

    @property
    def header(self):
        return self._header

    @property
    def store(self):
        return self._store

    @property
    def width(self):
        return self._width

class UIScreen(object):
    title = u"Screen.."

    def __init__(self, app):
        self._app = app
        self._window = []

    def refresh(self, args = None):
        """Method which prepares the screen to self._window. If user input is requested, return True."""
        self._window = [self.title, u""]

    @property
    def window(self):
        return self

    def show_all(self):
        for w in self._window:
            if hasattr(w, "render"):
                w.render(self.app.width)
            print unicode(w)

    show = show_all

    def hide(self):
        pass

    def input(self, key):
        """Method called to process input. If the input is not handled here, return it."""
        return key

    def prompt(self):
        """Return the text to be shown as prompt or handle the prompt and return None."""
        return u"\tPlease make your choice from above ['q' to quit]: "

    @property
    def app(self):
        return self._app

    def close(self):
        self.app.close_screen(self)

class Widget(object):
    def __init__(self, max_width = None, default = None):
        """Initializes base Widgets buffer.

           @param max_width server as a hint about screen size to write method with default arguments
           @type max_width int

           @param default string containing the default content to fill the buffer with
           @type default string
           """

        self._buffer = []
        if default:
            self._buffer = [[c for c in l] for l in default.split("\n")]
        self._max_width = max_width
        self._cursor = (0, 0) # row, col

    @property
    def height(self):
        return len(self._buffer)

    @property
    def width(self):
        return reduce(lambda acc,l: max(acc, len(l)), self._buffer, 0)

    def clear(self):
        """Clears this widgets buffer and resets cursor."""
        self._buffer = list()
        self._cursor = (0, 0)

    @property
    def content(self):
        """This has to return list (rows) of lists (columns) with one character elements."""
        return self._buffer

    def render(self, width = None):
        """This method has to redraw the widget's self._buffer.

           @param width the width of buffer requested by the caller
           @type width int

           This method will commonly call render of child widgets and then draw and write
           methods to copy their contents to self._buffer
           """
        self.clear()

    def __unicode__(self):
        return u"\n".join([u"".join(l) for l in self._buffer])

    def setxy(self, row, col):
        """Sets cursor position."""
        self._cursor = (row, col)

    @property
    def cursor(self):
        return self._cursor

    def setend(self):
        """Sets the cursor to first column in new line at the end."""
        self._cursor = (self.height, 0)

    def draw(self, w, row = None, col = None, block = False):
        """This method copies w widget's content to this widget's buffer at row, col position.

           @param w widget to take content from
           @type w class Widget

           @param row row number to start at (default is at the cursor position)
           @type row int

           @param col column number to start at (default is at the cursor position)
           @type col int

           @param block when printing newline, start at column col (True) or at column 0 (False)
           @type boolean
           """


        if row is None:
            row = self._cursor[0]

        if col is None:
            col = self._cursor[1]

        # fill up rows
        if self.height < row + w.height:
            for i in range(row + w.height - self.height):
                self._buffer.append(list())

        # append columns
        for l in range(row, row + w.height):
            l_len = len(self._buffer[l])
            w_len = len(w.content[l - row])
            if l_len < col + w_len:
                self._buffer[l] += ((col + w_len - l_len) * list(u" "))
            self._buffer[l][col:col + w_len] = w.content[l - row][:]

        if block:
            self._cursor = (row + w.height, col)
        else:
            self._cursor = (row + w.height, 0)

    def write(self, text, row = None, col = None, width = None, block = False):
        """This method emulates typing machine writing to this widget's buffer.

           @param text text to type
           @type text unicode

           @param row row number to start at (default is at the cursor position)
           @type row int

           @param col column number to start at (default is at the cursor position)
           @type col int

           @param width wrap at "col" + "width" column (default is at self._max_width)
           @type width int

           @param block when printing newline, start at column col (True) or at column 0 (False)
           @type boolean
           """

        if row is None:
            row = self._cursor[0]

        if col is None:
            col = self._cursor[1]

        if width is None:
            width = self._max_width - col

        x = row
        y = col

        # emulate typing machine
        for c in text:
            # if the line is not in buffer, create it
            if x >= len(self._buffer):
                for i in range(x - len(self._buffer) + 1):
                    self._buffer.append(list())

            # if the line's length is not enough, fill it with spaces
            if y >= len(self._buffer[x]):
                self._buffer[x] += ((y - len(self._buffer[x]) + 1) * list(u" "))

            # process newline
            if c == "\n":
                x += 1
                if block:
                    y = col
                else:
                    y = 0
                continue

            # "type" character
            self._buffer[x][y] = c

            # shift to the next char
            y += 1
            if y >= col + width:
                x += 1
                if block:
                    y = col
                else:
                    y = 0

        self._cursor = (x, y)

class HelloWorld(UIScreen):
    def show(self, args = None):
        print """Hello World\nquit by typing 'quit'"""
        return True

if __name__ == "__main__":
    a = App("Hello World")
    s = HelloWorld(a, None)
    a.schedule_screen(s)
    a.run()
