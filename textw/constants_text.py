#
# constants_text.py: text mode constants
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

from translate import _, N_

INSTALL_OK = 0
INSTALL_BACK = -1
INSTALL_NOOP = -2

TEXT_OK_STR = N_("OK")
TEXT_OK_CHECK  = "ok"
TEXT_OK_BUTTON = (_(TEXT_OK_STR), TEXT_OK_CHECK)

TEXT_CANCEL_STR = N_("Cancel")
TEXT_CANCEL_CHECK  = "cancel"
TEXT_CANCEL_BUTTON = (_(TEXT_CANCEL_STR), TEXT_CANCEL_CHECK)

TEXT_BACK_STR = N_("Back")
TEXT_BACK_CHECK = "back"
TEXT_BACK_BUTTON = (_(TEXT_BACK_STR), TEXT_BACK_CHECK)

TEXT_YES_STR = N_("Yes")
TEXT_YES_CHECK = "yes"
TEXT_YES_BUTTON = (_(TEXT_YES_STR), TEXT_YES_CHECK)

TEXT_NO_STR = N_("No")
TEXT_NO_CHECK = "no"
TEXT_NO_BUTTON = (_(TEXT_NO_STR), TEXT_NO_CHECK)

TEXT_F12_CHECK = "F12"


TRUE = 1
FALSE = 0
