#
# Copyright (C) 2013  Red Hat, Inc.
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
# Red Hat Author(s): Vratislav Podzimek <vpodzime@redhat.com>
#

"""
Helper module with functions for informing user we are waiting for random
data entropy.

"""

import time
import select
import sys
import termios
import errno
import math

from pyanaconda.progress import progress_message
from pyanaconda.constants import MAX_ENTROPY_WAIT
from pykickstart.constants import DISPLAY_MODE_GRAPHICAL
from blivet.util import get_current_entropy

from pyanaconda.i18n import _, P_

def wait_for_entropy(msg, desired_entropy, ksdata):
    """
    Show UI dialog/message for waiting for desired random data entropy.

    :param ksdata: kickstart data
    :type ksdata: pykickstart.base.BaseHandler
    :param desired_entropy: entropy level to wait for
    :type desired_entropy: int
    :returns: whether to force continuing regardless of the available entropy level
    :rtype: bool

    """

    if ksdata.displaymode.displayMode == DISPLAY_MODE_GRAPHICAL:
        # cannot import globally because GUI code may be missing for text mode
        # in some cases
        from pyanaconda.ui.gui.spokes.lib.entropy_dialog import run_entropy_dialog
        progress_message(_("The system needs more random data entropy"))
        return run_entropy_dialog(ksdata, desired_entropy)
    else:
        return _tui_wait(msg, desired_entropy)

def _tui_wait(msg, desired_entropy):
    """Tell user we are waiting for entropy"""

    print(msg)
    print(_("Entropy can be increased by typing randomly on keyboard"))
    print(_("After %d minutes, the installation will continue regardless of the "
            "amount of available entropy") % (MAX_ENTROPY_WAIT / 60))
    fd = sys.stdin.fileno()
    termios_attrs_changed = False

    try:
        old = termios.tcgetattr(fd)
        new = termios.tcgetattr(fd)
        new[3] = new[3] & ~termios.ICANON & ~termios.ECHO
        new[6][termios.VMIN] = 1
        termios.tcsetattr(fd, termios.TCSANOW, new)
        termios_attrs_changed = True
    except termios.error as term_err:
        if term_err.args[0] == errno.ENOTTY:
            # "Inappropriate ioctl for device" --> terminal attributes not supported
            pass
        else:
            raise

    # wait for the entropy to become high enough or time has run out
    cur_entr = get_current_entropy()
    secs = 0
    while cur_entr < desired_entropy and secs <= MAX_ENTROPY_WAIT:
        remaining = (MAX_ENTROPY_WAIT - secs) / 60.0
        print(_("Available entropy: %(av_entr)s, Required entropy: %(req_entr)s [%(pct)d %%] (%(rem)d %(min)s remaining)")
                % {"av_entr": cur_entr, "req_entr": desired_entropy,
                   "pct": int((float(cur_entr) / desired_entropy) * 100),
                   "min": P_("minute", "minutes", remaining),
                   "rem": math.ceil(remaining)})
        time.sleep(1)
        cur_entr = get_current_entropy()
        secs += 1

    # print the final state as well
    print(_("Available entropy: %(av_entr)s, Required entropy: %(req_entr)s [%(pct)d %%]")
            % {"av_entr": cur_entr, "req_entr": desired_entropy,
               "pct": int((float(cur_entr) / desired_entropy) * 100)})

    if secs <= MAX_ENTROPY_WAIT:
        print(_("Enough entropy gathered, please stop typing."))
        force_cont = False
    else:
        print(_("Giving up, time (%d minutes) ran out.") % (MAX_ENTROPY_WAIT / 60))
        force_cont = True

    # we are done
    # first let the user notice we are done and stop typing
    time.sleep(5)

    # and then just read everything from the input buffer and revert the
    # termios state
    data = "have something"
    while sys.stdin in select.select([sys.stdin], [], [], 0)[0] and data:
        # just read from stdin and scratch the read data
        data = sys.stdin.read(1)

    if termios_attrs_changed:
        termios.tcsetattr(fd, termios.TCSAFLUSH, old)

    return force_cont
