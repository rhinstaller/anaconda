#
# vnc.py: VNC related installer functionality
#
# Copyright 2004 Red Hat, Inc.
#
# Jeremy Katz <katzj@redhat.com>
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import os, sys, string
from snack import *
from constants_text import *
from rhpl.translate import _, N_

def radiocb(*args):
    pass

# return -1 to use text mode, None for no vncpass, or vncpass otherwise
def askVncWindow():
    screen = SnackScreen()
    vncpass = None
    vncconnect = 0

    STEP_MESSAGE = 0
    STEP_PASS = 1
    STEP_DONE = 3
    step = 0
    while step < STEP_DONE:
        if step == STEP_MESSAGE:
            button = ButtonChoiceWindow(screen, _("Unable to Start X"),
                                        _("X was unable to start on your "
                                          "machine.  Would you like to "
                                          "start VNC to connect to "
                                          "this computer from another "
                                          "computer and perform a "
                                          "graphical install or continue "
                                          "with a text mode install?"),
                                        buttons = [ _("Use text mode"),
                                                    _("Start VNC") ])
	    
	    if button == string.lower (_("Use text mode")):
                screen.finish()
                return -1
            else:
                step = STEP_PASS
                continue

        if step == STEP_PASS:
            grid = GridFormHelp(screen, _("VNC Configuration"),
                                "vnc", 1, 10)

            bb = ButtonBar(screen, (TEXT_OK_BUTTON,
                                    (_("No password"), "nopass"),
                                    TEXT_BACK_BUTTON))

            text = _("A password will prevent unauthorized listeners "
                     "connecting and monitoring your installation progress.  "
                     "Please enter a password to be used for the installation")
            grid.add(TextboxReflowed(40, text), 0, 0, (0, 0, 0, 1))

            entry1 = Entry (16, password = 1)
            entry2 = Entry (16, password = 1)
            passgrid = Grid (2, 2)
            passgrid.setField (Label (_("Password:")), 0, 0, (0, 0, 1, 0), anchorLeft = 1)
            passgrid.setField (Label (_("Password (confirm):")), 0, 1, (0, 0, 1, 0), anchorLeft = 1)
            passgrid.setField (entry1, 1, 0)
            passgrid.setField (entry2, 1, 1)
            grid.add (passgrid, 0, 1, (0, 0, 0, 1))

            grid.add(bb, 0, 8, (0, 1, 1, 0), growx = 1)

            while 1:
                res = grid.run()
                rc = bb.buttonPressed(res)

                if rc == TEXT_BACK_CHECK:
                    screen.popWindow()
                    step = STEP_MESSAGE
                    break
                elif rc == "nopass":
                    screen.finish()
                    return None
                else:
                    pw = entry1.value()
                    cf = entry2.value()
                    if pw != cf:
                        ButtonChoiceWindow(screen, _("Password Mismatch"),
                                           _("The passwords you entered were "
                                             "different. Please try again."),
                                           buttons = [ TEXT_OK_BUTTON ],
                                           width = 50)
                    elif len(pw) < 6:
                        ButtonChoiceWindow(screen, _("Password Length"),
                                           _("The password must be at least "
                                             "six characters long."),
                                           buttons = [ TEXT_OK_BUTTON ],
                                           width = 50)
                    else:
                        screen.finish()
                        return pw

                    entry1.set("")
                    entry2.set("")
                    continue
                continue

    screen.finish()
    return -1


if __name__ == "__main__":
    askVncWindow()
