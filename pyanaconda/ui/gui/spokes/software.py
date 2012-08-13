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

from pyanaconda.flags import flags

from pyanaconda.ui.gui import communication
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.spokes.lib.detailederror import DetailedErrorDialog
from pyanaconda.ui.gui.utils import enlightbox, gdk_threaded
from pyanaconda.ui.gui.categories.software import SoftwareCategory
from .source import AdditionalReposDialog

import sys

__all__ = ["SoftwareSelectionSpoke"]

class SoftwareSelectionSpoke(NormalSpoke):
    builderObjects = ["addonStore", "desktopStore", "softwareWindow"]
    mainWidgetName = "softwareWindow"
    uiFile = "spokes/software.glade"

    category = SoftwareCategory

    icon = "package-x-generic-symbolic"
    title = N_("SOFTWARE SELECTION")

    def __init__(self, *args, **kwargs):
        NormalSpoke.__init__(self, *args, **kwargs)
        self._errorMsgs = None
        self._tx_id = None

        self.selectedGroups = []
        self.excludedGroups = []
        self.desktop = None

        self._addRepoDialog = AdditionalReposDialog(self.data)

    def apply(self):
        # NOTE:  Other apply methods work directly with the ksdata, but this
        # one does not.  However, selectGroup/deselectGroup modifies ksdata as
        # part of its operation.  So this is fine.
        from pyanaconda.threads import threadMgr, AnacondaThread

        row = self._get_selected_desktop()
        if not row:
            return

        self.payload.data.packages.groupList = []
        self.payload.selectGroup(row[2])
        for group in self.selectedGroups:
            self.payload.selectGroup(group)

        # select some stuff people will want with their desktop
        # XXX this is only a placeholder until the new group metadata is in
        #     place
        if row[2] != "base":
            groups = ['base-x', 'fonts']
            for group in [g for g in groups if g not in self.excludedGroups]:
                self.payload.selectGroup(group)

        communication.send_not_ready(self.__class__.__name__)
        threadMgr.add(AnacondaThread(name="AnaCheckSoftwareThread",
                                     target=self.checkSoftwareSelection))

    def checkSoftwareSelection(self):
        from pyanaconda.packaging import DependencyError
        communication.send_message(self.__class__.__name__,
                                   _("Checking software dependencies..."))
        try:
            self.payload.checkSoftwareSelection()
        except DependencyError as e:
            self._errorMsgs = "\n".join(sorted(e.message))
            communication.send_message(self.__class__.__name__,
                                       _("Error checking software dependencies"))
            self._tx_id = None
        else:
            self._errorMsgs = None
            self._tx_id = self.payload.txID
        finally:
            communication.send_ready(self.__class__.__name__)

    @property
    def completed(self):
        from pyanaconda.threads import threadMgr
        from pyanaconda.kickstart import packagesSeen

        processingDone = not threadMgr.get("AnaCheckSoftwareThread") and \
                         not self._errorMsgs and \
                         self._tx_id == self.payload.txID

        if flags.automatedInstall:
            return packagesSeen and processingDone
        else:
            return self._get_selected_desktop() is not None and processingDone

    @property
    def ready(self):
        # By default, the software selection spoke is not ready.  We have to
        # wait until the installation source spoke is completed.  This could be
        # becasue the user filled something out, or because we're done fetching
        # repo metadata from the mirror list, or we detected a DVD/CD.
        from pyanaconda.threads import threadMgr
        return (not threadMgr.get("AnaSoftwareWatcher") and
                not threadMgr.get("AnaPayloadMDThread") and
                not threadMgr.get("AnaCheckSoftwareThread") and
                self.payload.baseRepo is not None)

    @property
    def status(self):
        from pyanaconda.kickstart import packagesSeen
        from pyanaconda.threads import threadMgr

        if self._errorMsgs:
            return _("Error checking software selection")

        if threadMgr.get("AnaPayloadMDThread") or self.payload.baseRepo is None:
            return _("Installation source not set up")

        row = self._get_selected_desktop()
        if not row:
            # Kickstart installs with %packages will have a row selected, unless
            # they did an install without a desktop environment.  This should
            # catch that one case.
            if flags.automatedInstall and packagesSeen:
                return _("Custom software selected")

            return _("Nothing selected")

        return self.payload.description(row[2])[0]

    def initialize(self):
        from pyanaconda.threads import threadMgr, AnacondaThread

        NormalSpoke.initialize(self)
        threadMgr.add(AnacondaThread(name="AnaSoftwareWatcher", target=self._initialize))

    def _initialize(self):
        from pyanaconda.packaging import MetadataError
        from pyanaconda.threads import threadMgr

        communication.send_message(self.__class__.__name__, _("Downloading package metadata..."))

        payloadThread = threadMgr.get("AnaPayloadThread")
        if payloadThread:
            payloadThread.join()

        communication.send_message(self.__class__.__name__, _("Downloading group metadata..."))

        with gdk_threaded():
            # Grabbing the list of groups could potentially take a long time the
            # first time (yum does a lot of magic property stuff, some of which
            # involves side effects like network access) so go ahead and grab
            # them once now.
            try:
                self.refresh()
            except MetadataError:
                communication.send_message(self.__class__.__name__,
                                           _("No installation source available"))
                return

            self.payload.release()

        communication.send_ready(self.__class__.__name__)

        # If packages were provided by an input kickstart file (or some other means),
        # we should do dependency solving here.
        self.apply()

    def refresh(self):
        from gi.repository import Gtk

        from pyanaconda.threads import threadMgr
        NormalSpoke.refresh(self)

        mdGatherThread = threadMgr.get("AnaPayloadMDThread")
        if mdGatherThread:
            mdGatherThread.join()

        self._desktopStore = self.builder.get_object("desktopStore")
        self._desktopStore.clear()
        self._addonStore = self.builder.get_object("addonStore")
        self._addonStore.clear()

        desktops = []
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
                    self.desktop = grp

                desktops.append(grp)
            else:
                (name, desc) = self.payload.description(grp)
                selected = self.payload.groupSelected(grp)

                self._addonStore.append([selected, "<b>%s</b>\n%s" % (name, desc), grp])

        self.selectedGroups = [g.name for g in self.data.packages.groupList
                                if g.name not in desktops]
        self.excludedGroups = [g.name
                                for g in self.data.packages.excludedGroupList]

        if self._errorMsgs:
            self.window.set_info(Gtk.MessageType.WARNING, _("Error checking software dependencies.  Click for details."))

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
        selected = not self._addonStore[path][0]
        group = self._addonStore[path][2]
        self._addonStore[path][0] = selected
        if selected:
            if group not in self.selectedGroups:
                self.selectedGroups.append(group)

            if group in self.excludedGroups:
                self.excludedGroups.remove(group)

        elif not selected and group in self.selectedGroups:
            self.selectedGroups.remove(group)

    def on_custom_clicked(self, button):
        with enlightbox(self.window, self._addRepoDialog.window):
            response =  self._addRepoDialog.run()

    def on_info_bar_clicked(self, *args):
        if not self._errorMsgs:
            return

        dialog = DetailedErrorDialog(self.data, buttons=[_("_Quit"), _("_Remove Packages"),
                                                         _("_Modify Software Source")])
        with enlightbox(self.window, dialog.window):
            dialog.refresh(self._errorMsgs)
            rc = dialog.run()

        dialog.window.destroy()

        if rc == 0:
            # Close the dialog so the user can change selections.
            pass
        elif rc == 1:
            # Quit.
            sys.exit(0)
        elif rc == 2:
            # TODO:  Attempt to remove the affected packages.
            pass
        elif rc == 3:
            # Send the user to the installation source spoke.
            self.skipTo = "SourceSpoke"
            self.window.emit("back-clicked")
