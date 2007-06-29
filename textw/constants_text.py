#
# constants_text.py: text mode constants
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

from rhpl.translate import _, N_

INSTALL_OK = 0
INSTALL_BACK = -1
INSTALL_NOOP = -2

class Translator:
    """A simple class to facilitate on-the-fly translation for newt buttons"""
    def __init__(self, button, check):
        self.button = button
        self.check = check

    def __getitem__(self, which):
        if which == 0:
            return _(self.button)
        elif which == 1:
            return self.check
        raise IndexError

    def __len__(self):
        return 2

TEXT_OK_STR = N_("OK")
TEXT_OK_CHECK  = "ok"
TEXT_OK_BUTTON = Translator(TEXT_OK_STR, TEXT_OK_CHECK)

TEXT_CANCEL_STR = N_("Cancel")
TEXT_CANCEL_CHECK  = "cancel"
TEXT_CANCEL_BUTTON = Translator(TEXT_CANCEL_STR, TEXT_CANCEL_CHECK)

TEXT_BACK_STR = N_("Back")
TEXT_BACK_CHECK = "back"
TEXT_BACK_BUTTON = Translator(TEXT_BACK_STR, TEXT_BACK_CHECK)

TEXT_YES_STR = N_("Yes")
TEXT_YES_CHECK = "yes"
TEXT_YES_BUTTON = Translator(TEXT_YES_STR, TEXT_YES_CHECK)

TEXT_NO_STR = N_("No")
TEXT_NO_CHECK = "no"
TEXT_NO_BUTTON = Translator(TEXT_NO_STR, TEXT_NO_CHECK)

TEXT_EDIT_STR = N_("Edit")
TEXT_EDIT_CHECK = "edit"
TEXT_EDIT_BUTTON = Translator(TEXT_EDIT_STR, TEXT_EDIT_CHECK)

TEXT_F12_CHECK = "F12"

TRUE = 1
FALSE = 0
