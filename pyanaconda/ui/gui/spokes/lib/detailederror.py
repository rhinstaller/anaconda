# Detailed error dialog class
#
# Copyright (C) 2011-2012  Red Hat, Inc.
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
# Red Hat Author(s): Chris Lumens <clumens@redhat.com>
#

from pyanaconda.i18n import _
from pyanaconda.ui.gui import GUIObject

__all__ = ["DetailedErrorDialog"]

class DetailedErrorDialog(GUIObject):
    """This class provides a lightboxable dialog to display a very detailed
       set of error messages, like might be required to display the results
       of package dependency solving or storage sanity checking.

       If no buttons are provided, this dialog will have only a single button:
       cancel, with a response ID of 0.  Otherwise, the kwarg named "buttons"
       should be a list of translated labels.  Each will have an incrementing
       response ID starting with 0, and any Quit button will be placed on the
       far left hand side of the dialog.  It's up to the caller of the "run"
       method to do something with the returned response ID.
    """
    builderObjects = ["detailedErrorDialog", "detailedTextBuffer"]
    mainWidgetName = "detailedErrorDialog"
    uiFile = "spokes/lib/detailederror.glade"

    def __init__(self, *args, **kwargs):
        buttons = kwargs.pop("buttons", [])
        label = kwargs.pop("label", None)
        GUIObject.__init__(self, *args, **kwargs)

        if not buttons:
            widget = self.window.add_button(_("_Cancel"), 0)
        else:
            buttonbox = self.builder.get_object("detailedButtonBox")
            i = 0

            for button in buttons:
                widget = self.window.add_button(button, i)

                # Quit buttons should always appear left-most, unless it's the
                # only button.  Then it should appear on the right.
                if button == _("_Quit") and len(buttons) > 1:
                    buttonbox.set_child_secondary(widget, True)

                i += 1

        widget.set_can_default(True)
        widget.grab_default()

        if label:
            self.builder.get_object("detailedLabel").set_text(label)

    # pylint: disable-msg=W0221
    def refresh(self, msg):
        buf = self.builder.get_object("detailedTextBuffer")
        buf.set_text(msg, -1)

    def run(self):
        return self.window.run()
