# Software selection spoke classes
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

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)
N_ = lambda x: x

from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.utils import gdk_threaded
from pyanaconda.ui.gui.categories.software import SoftwareCategory

__all__ = ["SoftwareSelectionSpoke"]

class SoftwareSelectionSpoke(NormalSpoke):
    builderObjects = ["addonStore", "desktopStore", "softwareWindow"]
    mainWidgetName = "softwareWindow"
    uiFile = "spokes/software.ui"

    category = SoftwareCategory

    icon = "package-x-generic-symbolic"
    title = N_("SOFTWARE SELECTION")

    def __init__(self, *args, **kwargs):
        NormalSpoke.__init__(self, *args, **kwargs)
        self._ready = False

    def apply(self):
        row = self._get_selected_desktop()
        if not row:
            return

        self.payload.selectGroup(row[2])

        for row in self._addonStore:
            if row[0]:
                self.payload.selectGroup(row[2])
            else:
                self.payload.deselectGroup(row[2])

    @property
    def completed(self):
        return self._get_selected_desktop() is not None

    @property
    def ready(self):
        # By default, the software selection spoke is not ready.  We have to
        # wait until the installation source spoke is completed.  This could be
        # becasue the user filled something out, or because we're done fetching
        # repo metadata from the mirror list, or we detected a DVD/CD.
        return self._ready

    @property
    def status(self):
        row = self._get_selected_desktop()
        if not row:
            return _("Nothing selected")

        return self.payload.description(row[2])[0]

    def initialize(self):
        from pyanaconda.threads import threadMgr
        from threading import Thread

        threadMgr.add(Thread(name="AnaSoftwareWatcher", target=self._initialize))

    def _initialize(self):
        from pyanaconda.threads import threadMgr

        payloadThread = threadMgr.get("AnaPayloadThread")
        if payloadThread:
            payloadThread.join()

        with gdk_threaded():
            self._ready = True
            self.selector.set_sensitive(True)

            # Grabbing the list of groups could potentially take a long time the
            # first time (yum does a lot of magic property stuff, some of which
            # involves side effects like network access) so go ahead and grab
            # them once now.
            self.refresh()
            self.payload.release()

    def refresh(self):
        NormalSpoke.refresh(self)

        self._desktopStore = self.builder.get_object("desktopStore")
        self._desktopStore.clear()
        self._addonStore = self.builder.get_object("addonStore")
        self._addonStore.clear()

        for grp in self.payload.groups:
            # Throw out language support groups and critical-path stuff.
            if grp.endswith("-support") or grp.startswith("critical-path-"):
                continue
            # Throw out core, which should always be selected.
            elif grp == "core":
                continue
            elif grp == "base" or grp.endswith("-desktop"):
                (name, desc) = self.payload.description(grp)
                selected = self.payload.groupSelected(grp)

                itr = self._desktopStore.append([selected, "<b>%s</b>\n%s" % (name, desc), grp])
                if selected:
                    sel = self.builder.get_object("desktopSelector")
                    sel.select_iter(itr)
            else:
                (name, desc) = self.payload.description(grp)
                selected = self.payload.groupSelected(grp)

                self._addonStore.append([selected, "<b>%s</b>\n%s" % (name, desc), grp])

    # Returns the row in the store corresponding to what's selected on the
    # left hand panel, or None if nothing's selected.
    def _get_selected_desktop(self):
        desktopView = self.builder.get_object("desktopView")
        (store, itr) = desktopView.get_selection().get_selected()
        if not itr:
            return None

        return self._desktopStore[itr]

    # Signal handlers
    def on_row_toggled(self, renderer, path):
        self._addonStore[path][0] = not self._addonStore[path][0]

    def on_custom_clicked(self, button):
        # FIXME: does nothing for now
        pass
