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
from pyanaconda.kickstart import packagesSeen
from pyanaconda.threads import threadMgr, AnacondaThread

from pyanaconda.ui.gui import communication
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.spokes.lib.detailederror import DetailedErrorDialog
from pyanaconda.ui.gui.utils import enlightbox, gtk_thread_wait
from pyanaconda.ui.gui.categories.software import SoftwareCategory
from .source import AdditionalReposDialog

from pykickstart.parser import Group

from gi.repository import GLib

import sys

__all__ = ["SoftwareSelectionSpoke"]

class SoftwareSelectionSpoke(NormalSpoke):
    builderObjects = ["addonStore", "environmentStore", "softwareWindow"]
    mainWidgetName = "softwareWindow"
    uiFile = "spokes/software.glade"

    category = SoftwareCategory

    icon = "package-x-generic-symbolic"
    title = N_("SOFTWARE SELECTION")

    def __init__(self, *args, **kwargs):
        NormalSpoke.__init__(self, *args, **kwargs)
        self._errorMsgs = None
        self._tx_id = None
        self._selectFlag = False

        self.selectedGroups = []
        self.excludedGroups = []
        self.environment = None

        self._addRepoDialog = AdditionalReposDialog(self.data)

        # Used for detecting whether anything's changed in the spoke.
        self._clickedRemove = False
        self._origAddons = []
        self._origEnvironment = None

    def apply(self):
        # NOTE:  Other apply methods work directly with the ksdata, but this
        # one does not.  However, selectGroup/deselectGroup modifies ksdata as
        # part of its operation.  So this is fine.
        row = self._get_selected_environment()
        if not row:
            return

        addons = self._get_selected_addons()

        # Don't redo dep solving if nothing's changed.
        if row[2] == self._origEnvironment and set(addons) == set(self._origAddons) and \
           not self._clickedRemove and self.txid_valid:
            return

        self._selectFlag = False
        self.payload.data.packages.groupList = []
        self.payload.selectEnvironment(row[2])
        self.environment = row[2]
        for group in self.selectedGroups:
            self.payload.selectGroup(group)

        # And then save these values so we can check next time.
        self._clickedRemove = False
        self._origAddons = addons
        self._origEnvironment = self.environment

        communication.send_not_ready(self.__class__.__name__)
        communication.send_not_ready("SourceSpoke")
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
            communication.send_ready("SourceSpoke")

    @property
    def completed(self):
        processingDone = not threadMgr.get("AnaCheckSoftwareThread") and \
                         not self._errorMsgs and self.txid_valid

        if flags.automatedInstall and packagesSeen:
            return processingDone
        else:
            return self._get_selected_environment() is not None and processingDone

    @property
    def ready(self):
        # By default, the software selection spoke is not ready.  We have to
        # wait until the installation source spoke is completed.  This could be
        # because the user filled something out, or because we're done fetching
        # repo metadata from the mirror list, or we detected a DVD/CD.
        return (not threadMgr.get("AnaSoftwareWatcher") and
                not threadMgr.get("AnaPayloadMDThread") and
                not threadMgr.get("AnaCheckSoftwareThread") and
                self.payload.baseRepo is not None)

    @property
    def showable(self):
        return not flags.livecdInstall

    @property
    def status(self):
        if self._errorMsgs:
            return _("Error checking software selection")

        if not self.ready:
            return _("Installation source not set up")

        if not self.txid_valid:
            return _("Source changed - please verify")

        row = self._get_selected_environment()
        if not row:
            # Kickstart installs with %packages will have a row selected, unless
            # they did an install without a desktop environment.  This should
            # catch that one case.
            if flags.automatedInstall and packagesSeen:
                return _("Custom software selected")

            return _("Nothing selected")

        return self.payload.environmentDescription(row[2])[0]

    def initialize(self):
        NormalSpoke.initialize(self)
        threadMgr.add(AnacondaThread(name="AnaSoftwareWatcher", target=self._initialize))

    def _initialize(self):
        communication.send_message(self.__class__.__name__, _("Downloading package metadata..."))

        payloadThread = threadMgr.get("AnaPayloadThread")
        if payloadThread:
            payloadThread.join()

        communication.send_message(self.__class__.__name__, _("Downloading group metadata..."))

        # we have no way to select environments with kickstart right now
        # so don't try.
        if flags.automatedInstall and packagesSeen:
            # We don't want to do a full refresh, just
            # join the metadata thread
            mdGatherThread = threadMgr.get("AnaPayloadMDThread")
            if mdGatherThread:
                mdGatherThread.join()
        else:
            if not self._first_refresh():
                return
        self.payload.release()

        communication.send_ready(self.__class__.__name__)

        # If packages were provided by an input kickstart file (or some other means),
        # we should do dependency solving here.
        self.apply()

    @gtk_thread_wait
    def _first_refresh(self):
        # Grabbing the list of groups could potentially take a long time the
        # first time (yum does a lot of magic property stuff, some of which
        # involves side effects like network access) so go ahead and grab
        # them once now.
        from pyanaconda.packaging import MetadataError

        try:
            self.refresh()
            return True
        except MetadataError:
            communication.send_message(self.__class__.__name__,
                                       _("No installation source available"))
            return False

    def refresh(self):
        NormalSpoke.refresh(self)

        mdGatherThread = threadMgr.get("AnaPayloadMDThread")
        if mdGatherThread:
            mdGatherThread.join()

        self._environmentStore = self.builder.get_object("environmentStore")
        self._environmentStore.clear()

        clasess = []
        firstEnvironment = True
        for environment in self.payload.environments:
            (name, desc) = self.payload.environmentDescription(environment)

            itr = self._environmentStore.append([environment == self.environment, "<b>%s</b>\n%s" % (name, desc), environment])
            # Either:
            # (1) Select the environment given by kickstart or selected last
            #     time this spoke was displayed; or
            # (2) Select the first environment given by display order as the
            #     default if nothing is selected.
            if (environment == self.environment) or \
               (not self.environment and firstEnvironment):
                sel = self.builder.get_object("environmentSelector")
                sel.select_iter(itr)
                self.environment = environment

            firstEnvironment = False

        self.refreshAddons()

    def refreshAddons(self):
        from gi.repository import Gtk

        self._addonStore = self.builder.get_object("addonStore")
        self._addonStore.clear()
        if self.environment:
            for grp in self.payload.groups:
                if self.payload.environmentHasOption(self.environment, grp) or (self.payload._isGroupVisible(grp) and self.payload._groupHasInstallableMembers(grp)):
                    (name, desc) = self.payload.groupDescription(grp)
                    selected = grp in self.selectedGroups

                    self._addonStore.append([selected, "<b>%s</b>\n%s" % (name, desc), grp])

        self._selectFlag = True

        if self._errorMsgs:
            self.set_warning(_("Error checking software dependencies.  Click for details."))
        else:
            self.clear_info()

    def _get_selected_addons(self):
        return [row[2] for row in self._addonStore if row[0]]

    # Returns the row in the store corresponding to what's selected on the
    # left hand panel, or None if nothing's selected.
    def _get_selected_environment(self):
        environmentView = self.builder.get_object("environmentView")
        (store, itr) = environmentView.get_selection().get_selected()
        if not itr:
            return None

        return self._environmentStore[itr]

    @property
    def txid_valid(self):
        return self._tx_id == self.payload.txID

    # Signal handlers
    def on_environment_toggled(self, renderer, path):
        if not self._selectFlag:
            return

        # First, mark every row as unselected so the radio button on whatever
        # row was previously selected will be cleared out.
        for row in self._environmentStore:
            row[0] = False

        # Then, remove all the groups that were selected by the previously
        # selected environment.
        for groupid in self.payload.environmentGroups(self.environment):
            if groupid in self.selectedGroups:
                self.selectedGroups.remove(groupid)

        # Then mark the clicked environment as selected and update the screen.
        self._environmentStore[path][0] = True
        self.environment = self._environmentStore[path][2]
        self.refreshAddons()

    def on_addon_toggled(self, renderer, path):
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

        label = _("The following software marked for installation has errors.  "
                  "This is likely caused by an error with\nyour installation source.  "
                  "You can attempt to remove these packages from your installation.\n"
                  "change your installation source, or quit the installer.")
        dialog = DetailedErrorDialog(self.data, buttons=[_("_Quit"), _("_Cancel"),
                                                         _("_Remove Packages"),
                                                         _("_Modify Software Source")],
                                                label=label)
        with enlightbox(self.window, dialog.window):
            dialog.refresh(self._errorMsgs)
            rc = dialog.run()

        dialog.window.destroy()

        if rc == 0:
            # Quit.
            sys.exit(0)
        elif rc == 1:
            # Close the dialog so the user can change selections.
            pass
        elif rc == 2:
            # This setting is just so we know to try re-resolving dependencies
            # even if the user didn't change any other settings.
            self._clickedRemove = True

            # Attempt to remove the affected packages.  For yum payloads, we
            # do this by just attempting to re-resolve dependencies with
            # skip_broken set.
            self._errorMsgs = None
            self.payload.skipBroken = True
            self.window.emit("button-clicked")
        elif rc == 3:
            # Send the user to the installation source spoke.
            self.skipTo = "SourceSpoke"
            self.window.emit("button-clicked")
