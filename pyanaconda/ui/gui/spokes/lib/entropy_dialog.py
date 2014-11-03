# Dialog for waiting for enough random data entropy
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

import time
import math

from gi.repository import Gtk, GLib

from pyanaconda.i18n import P_
from pyanaconda.constants import MAX_ENTROPY_WAIT
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.utils import gtk_action_wait
from blivet.util import get_current_entropy

__all__ = ["run_entropy_dialog"]

# in milliseconds
LOOP_TIMEOUT = 250

@gtk_action_wait
def run_entropy_dialog(ksdata, desired_entropy):
    """Show dialog with waiting for entropy"""

    dialog = EntropyDialog(ksdata, desired_entropy)
    dialog.run()

    return dialog.force_cont

class EntropyDialog(GUIObject):
    builderObjects = ["entropyDialog"]
    mainWidgetName = "entropyDialog"
    uiFile = "spokes/lib/entropy_dialog.glade"

    def __init__(self, data, desired_entropy):
        GUIObject.__init__(self, data)
        self._desired_entropy = desired_entropy
        self._progress_bar = self.builder.get_object("progressBar")
        self._terminate = False
        self._started = 0
        self.force_cont = False
        self._num_loops = 0

    def run(self):
        self.window.show_all()

        # XXX: Is it better to rely on Gtk running the self._update_progress
        # method every ~250msec or rely on NTP not changing system time right
        # now and use time.time()?
        self._num_loops = 0
        GLib.timeout_add(LOOP_TIMEOUT, self._update_progress)
        Gtk.main()
        self.window.destroy()

    def _update_progress(self):
        if self._terminate:
            # give users time to realize they should stop typing
            time.sleep(3)
            Gtk.main_quit()
            # remove the method from idle queue
            return False
        else:
            self._num_loops += 1
            current_entropy = get_current_entropy()
            current_fraction = min(float(current_entropy) / self._desired_entropy, 1.0)
            remaining = (MAX_ENTROPY_WAIT * 1000 - self._num_loops * LOOP_TIMEOUT) / 1000 / 60.0

            self._progress_bar.set_fraction(current_fraction)
            self._progress_bar.set_text("%(pct)d %% (%(rem)d %(min)s remaining)" % {"pct": (int(current_fraction * 100)),
                                                                                    "rem": math.ceil(remaining),
                                                                                    "min": P_("minute", "minutes", int(remaining))})

            # if we have enough our time ran out, terminate the dialog, but let
            # the progress_bar refresh in the main loop
            self._terminate = (current_entropy >= self._desired_entropy) or (remaining <= 0)

            self.force_cont = (remaining <= 0)

            # keep updating
            return True

