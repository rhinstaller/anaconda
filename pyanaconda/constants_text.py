#
# constants_text.py: text mode constants
#
# Copyright (C) 2000, 2001, 2002  Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

# pylint: disable=wildcard-import
from pyanaconda.constants import *
from pyanaconda.i18n import _, N_

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
TEXT_CANCEL_CHECK = "cancel"
TEXT_CANCEL_BUTTON = Translator(TEXT_CANCEL_STR, TEXT_CANCEL_CHECK)

TEXT_YES_STR = N_("Yes")
TEXT_YES_CHECK = "yes"
TEXT_YES_BUTTON = Translator(TEXT_YES_STR, TEXT_YES_CHECK)

TEXT_NO_STR = N_("No")
TEXT_NO_CHECK = "no"
TEXT_NO_BUTTON = Translator(TEXT_NO_STR, TEXT_NO_CHECK)

# Make the return calls from the UIScreen input() function more clear
INPUT_PROCESSED = None
INPUT_DISCARDED = False
