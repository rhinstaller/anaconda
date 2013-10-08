# The base classes for Anaconda TUI Spokes
#
# Copyright (C) (2012)  Red Hat, Inc.
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
from pyanaconda.ui.tui import simpleline as tui
from pyanaconda.ui.tui.tuiobject import TUIObject, YesNoDialog
from pyanaconda.ui.common import Spoke, StandaloneSpoke, NormalSpoke, PersonalizationSpoke, collect
from pyanaconda.users import validatePassword, cryptPassword
import re
from collections import namedtuple
from pyanaconda.iutil import setdeepattr, getdeepattr
from pyanaconda.i18n import _
from pyanaconda.constants import PASSWORD_CONFIRM_ERROR_TUI

__all__ = ["TUISpoke", "EditTUISpoke", "EditTUIDialog", "EditTUISpokeEntry", "StandaloneSpoke", "NormalSpoke", "PersonalizationSpoke",
           "collect_spokes", "collect_categories"]

class TUISpoke(TUIObject, tui.Widget, Spoke):
    """Base TUI Spoke class implementing the pyanaconda.ui.common.Spoke API.
    It also acts as a Widget so we can easily add it to Hub, where is shows
    as a summary box with title, description and completed checkbox.

    :param title: title of this spoke
    :type title: unicode

    :param category: category this spoke belongs to
    :type category: string
    """

    title = _("Default spoke title")
    category = u""

    def __init__(self, app, data, storage, payload, instclass):
        TUIObject.__init__(self, app, data)
        tui.Widget.__init__(self)
        Spoke.__init__(self, data, storage, payload, instclass)

    @property
    def status(self):
        return _("testing status...")

    @property
    def completed(self):
        return True

    def refresh(self, args = None):
        TUIObject.refresh(self, args)
        return True

    def input(self, args, key):
        """Handle the input, the base class just forwards it to the App level."""
        return key

    def render(self, width):
        """Render the summary representation for Hub to internal buffer."""
        tui.Widget.render(self, width)

        if self.mandatory and not self.completed:
            key = "!"
        else:
            key = "x"

        # always set completed = True here; otherwise key value won't be
        # displayed if completed (spoke value from above) is False
        c = tui.CheckboxWidget(key = key, completed = True,
                               title = self.title, text = self.status)
        c.render(width)
        self.draw(c)

class NormalTUISpoke(TUISpoke, NormalSpoke):
    pass

EditTUISpokeEntry = namedtuple("EditTUISpokeEntry", ["title", "attribute", "aux", "visible"])

class EditTUIDialog(NormalTUISpoke):
    """Spoke/dialog used to read new value of textual or password data"""

    title = _("New value")
    PASSWORD = re.compile(".*")

    def __init__(self, app, data, storage, payload, instclass):
        NormalTUISpoke.__init__(self, app, data, storage, payload, instclass)
        self.value = None

    def refresh(self, args = None):
        self._window = []
        self.value = None
        return True

    def prompt(self, entry = None):
        if not entry:
            return None

        if entry.aux == self.PASSWORD:
            pw = self._app.raw_input(_("%s: ") % entry.title, hidden=True)
            confirm = self._app.raw_input(_("%s (confirm): ") % entry.title, hidden=True)

            if (pw and not confirm) or (confirm and not pw):
                print(_("You must enter your root password and confirm it by typing"
                        " it a second time to continue."))
                return None
            if (pw != confirm):
                print(_(PASSWORD_CONFIRM_ERROR_TUI))
                return None

            valid, strength, message = validatePassword(pw, user=None)

            if not valid:
                print(message)
                return None

            if strength < 50:
                if message:
                    error = _("You have provided a weak password: %s\n"
                              "Would you like to use it anyway?") % message
                else:
                    error = _("You have provided a weak password.\n"
                              "Would you like to use it anyway?")
                question_window = YesNoDialog(self._app, error)
                self._app.switch_screen_modal(question_window)
                if not question_window.answer:
                    return None

            self.value = cryptPassword(pw)
            return None
        else:
            return _("Enter new value for '%s' and press enter\n") % entry.title

    def input(self, entry, key):
        if entry.aux.match(key):
            self.value = key
            self.close()
            return True
        else:
            return NormalTUISpoke.input(self, entry, key)

class OneShotEditTUIDialog(EditTUIDialog):
    """The same as EditTUIDialog, but closes automatically after
       the value is read
    """

    def prompt(self, entry = None):
        ret = None

        if entry:
            ret = EditTUIDialog.prompt(self, entry)
            if ret is None:
                self.close()

        return ret

class EditTUISpoke(NormalTUISpoke):
    """Spoke with declarative semantics, it contains
       a list of titles, attribute names and regexps
       that specify the fields of an object the user
       allowed to edit.
    """

    # self.data's subattribute name
    # empty string means __init__ will provide
    # something else
    edit_data = ""

    # constants to be used in the aux field
    # and mark the entry as a password or checkbox field
    PASSWORD = EditTUIDialog.PASSWORD
    CHECK = "check"

    # list of fields in the format of named tuples like:
    # EditTUISpokeEntry(title, attribute, aux, visible)
    # title     - Nontranslated title of the entry
    # attribute - The edited object's attribute name
    # aux       - Compiled regular expression or one of the
    #             two constants from above.
    #             It will be used to check the value typed
    #             by user and to show the proper entry
    #             for password, text or checkbox.
    # visible   - True, False or a function that accepts
    #             two arguments - self and the edited object
    #             It is evaluated and used to display or
    #             hide this attribute's entry
    edit_fields = [
    ]

    def __init__(self, app, data, storage, payload, instclass):
        NormalTUISpoke.__init__(self, app, data, storage, payload, instclass)
        self.dialog = OneShotEditTUIDialog(app, data, storage, payload, instclass)

        # self.args should hold the object this Spoke is supposed
        # to edit
        self.args = None

    def refresh(self, args = None):
        NormalTUISpoke.refresh(self, args)

        if args:
            self.args = args
        elif self.edit_data:
            self.args = self.data
            for key in self.edit_data.split("."):
                self.args = getattr(self.args, key)

        def _prep_text(i, entry):
            number = tui.TextWidget("%2d)" % i)
            title = tui.TextWidget(_(entry.title))
            value = getdeepattr(self.args, entry.attribute)
            value = tui.TextWidget(value)

            return tui.ColumnWidget([(3, [number]), (None, [title, value])], 1)

        def _prep_check(i, entry):
            number = tui.TextWidget("%2d)" % i)
            value = getdeepattr(self.args, entry.attribute)
            ch = tui.CheckboxWidget(title=_(entry.title), completed=bool(value))

            return tui.ColumnWidget([(3, [number]), (None, [ch])], 1)

        def _prep_password(i, entry):
            number = tui.TextWidget("%2d)" % i)
            title = tui.TextWidget(_(entry.title))
            value = ""
            if len(getdeepattr(self.args, entry.attribute)) > 0:
                value = _("Password set.")
            value = tui.TextWidget(value)

            return tui.ColumnWidget([(3, [number]), (None, [title, value])], 1)

        for idx,entry in enumerate(self.edit_fields):
            if callable(entry.visible) and not entry.visible(self, self.args):
                continue
            elif not callable(entry.visible) and not entry.visible:
                continue

            entry_type = entry.aux
            if entry_type == self.PASSWORD:
                w = _prep_password(idx+1, entry)
            elif entry_type == self.CHECK:
                w = _prep_check(idx+1, entry)
            else:
                w = _prep_text(idx+1, entry)

            self._window.append(w)

        return True

    def input(self, args, key):
        try:
            idx = int(key) - 1
            if idx >= 0 and idx < len(self.edit_fields):
                if self.edit_fields[idx].aux == self.CHECK:
                    setdeepattr(self.args, self.edit_fields[idx].attribute,
                                not getdeepattr(self.args, self.edit_fields[idx][1]))
                    self.app.redraw()
                    self.apply()
                else:
                    self.app.switch_screen_modal(self.dialog, self.edit_fields[idx])
                    if self.dialog.value is not None:
                        setdeepattr(self.args, self.edit_fields[idx].attribute,
                                    self.dialog.value)
                        self.apply()
                return True
        except ValueError:
            pass

        return NormalTUISpoke.input(self, args, key)

class StandaloneTUISpoke(TUISpoke, StandaloneSpoke):
    pass

class PersonalizationTUISpoke(TUISpoke, PersonalizationSpoke):
    pass

def collect_spokes(mask_paths, category):
    """Return a list of all spoke subclasses that should appear for a given
       category.
    """
    spokes = []
    for mask, path in mask_paths:
        spokes.extend(collect(mask, path, lambda obj: hasattr(obj, "category") and obj.category != None and obj.category == category))
        
    return spokes
        
def collect_categories(mask_paths):
    classes = []
    for mask, path in mask_paths:
        classes.extend(collect(mask, path, lambda obj: hasattr(obj, "category") and obj.category != None and obj.category != ""))
        
    categories = set(c.category for c in classes)
    return categories
