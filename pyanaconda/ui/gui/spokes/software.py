# Software selection spoke classes
#
# Copyright (C) 2011-2013  Red Hat, Inc.
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

from gi.repository import Gdk

from pyanaconda.flags import flags
from pyanaconda.i18n import _, N_
from pyanaconda.packaging import MetadataError
from pyanaconda.threads import threadMgr, AnacondaThread
from pyanaconda import constants

from pyanaconda.ui.communication import hubQ
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.spokes.lib.detailederror import DetailedErrorDialog
from pyanaconda.ui.gui.utils import enlightbox, gtk_action_wait
from pyanaconda.ui.gui.categories.software import SoftwareCategory

import sys

__all__ = ["SoftwareSelectionSpoke"]

class SoftwareSelectionSpoke(NormalSpoke):
    builderObjects = ["addonStore", "environmentStore", "softwareWindow"]
    mainWidgetName = "softwareWindow"
    uiFile = "spokes/software.glade"

    category = SoftwareCategory

    icon = "package-x-generic-symbolic"
    title = N_("_SOFTWARE SELECTION")

    def __init__(self, *args, **kwargs):
        NormalSpoke.__init__(self, *args, **kwargs)
        self._errorMsgs = None
        self._tx_id = None
        self._selectFlag = False

        self.selectedGroups = []
        self.excludedGroups = []
        self.environment = None

        self._addonStore = self.builder.get_object("addonStore")
        self._environmentStore = self.builder.get_object("environmentStore")

        # Used for detecting whether anything's changed in the spoke.
        self._origAddons = []
        self._origEnvironment = None

        # We need to tell the addon view whether something is a separator or not.
        self.builder.get_object("addonView").set_row_separator_func(self._addon_row_is_separator, None)

    def _apply(self):
        row = self._get_selected_environment()
        if not row:
            return

        addons = self._get_selected_addons()
        for group in addons:
            if group not in self.selectedGroups:
                self.selectedGroups.append(group)

        self._selectFlag = False
        self.payload.data.packages.groupList = []
        self.payload.selectEnvironment(row[2])
        self.environment = row[2]
        for group in self.selectedGroups:
            self.payload.selectGroup(group)

        # And then save these values so we can check next time.
        self._origAddons = addons
        self._origEnvironment = self.environment

        hubQ.send_not_ready(self.__class__.__name__)
        hubQ.send_not_ready("SourceSpoke")
        threadMgr.add(AnacondaThread(name=constants.THREAD_CHECK_SOFTWARE,
                                     target=self.checkSoftwareSelection))

    def apply(self):
        self._apply()
        self.data.packages.seen = True

    def checkSoftwareSelection(self):
        from pyanaconda.packaging import DependencyError
        hubQ.send_message(self.__class__.__name__, _("Checking software dependencies..."))
        try:
            self.payload.checkSoftwareSelection()
        except DependencyError as e:
            self._errorMsgs = "\n".join(sorted(e.message))
            hubQ.send_message(self.__class__.__name__, _("Error checking software dependencies"))
            self._tx_id = None
        else:
            self._errorMsgs = None
            self._tx_id = self.payload.txID
        finally:
            hubQ.send_ready(self.__class__.__name__, False)
            hubQ.send_ready("SourceSpoke", False)

    @property
    def completed(self):
        processingDone = not threadMgr.get(constants.THREAD_CHECK_SOFTWARE) and \
                         not self._errorMsgs and self.txid_valid

        if flags.automatedInstall:
            return processingDone and self.data.packages.seen
        else:
            return self._get_selected_environment() is not None and processingDone

    @property
    def changed(self):
        row = self._get_selected_environment()
        if not row:
            return True

        addons = self._get_selected_addons()

        # Don't redo dep solving if nothing's changed.
        if row[2] == self._origEnvironment and set(addons) == set(self._origAddons) and \
           self.txid_valid:
            return False

        return True

    @property
    def mandatory(self):
        return True

    @property
    def ready(self):
        # By default, the software selection spoke is not ready.  We have to
        # wait until the installation source spoke is completed.  This could be
        # because the user filled something out, or because we're done fetching
        # repo metadata from the mirror list, or we detected a DVD/CD.

        return (not threadMgr.get(constants.THREAD_SOFTWARE_WATCHER) and
                not threadMgr.get(constants.THREAD_PAYLOAD_MD) and
                not threadMgr.get(constants.THREAD_CHECK_SOFTWARE) and
                self.payload.baseRepo is not None)

    @property
    def showable(self):
        return not flags.livecdInstall and not self.data.method.method == "liveimg"

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
            if flags.automatedInstall and self.data.packages.seen:
                return _("Custom software selected")

            return _("Nothing selected")

        return self.payload.environmentDescription(row[2])[0]

    def initialize(self):
        NormalSpoke.initialize(self)
        threadMgr.add(AnacondaThread(name=constants.THREAD_SOFTWARE_WATCHER,
                      target=self._initialize))

    def _initialize(self):
        hubQ.send_message(self.__class__.__name__, _("Downloading package metadata..."))

        threadMgr.wait(constants.THREAD_PAYLOAD)

        hubQ.send_message(self.__class__.__name__, _("Downloading group metadata..."))

        # we have no way to select environments with kickstart right now
        # so don't try.
        if flags.automatedInstall and self.data.packages.seen:
            # We don't want to do a full refresh, just join the metadata thread
            threadMgr.wait(constants.THREAD_PAYLOAD_MD)
        else:
            # Grabbing the list of groups could potentially take a long time
            # at first (yum does a lot of magic property stuff, some of which
            # involves side effects like network access.  We need to reference
            # them here, outside of the main thread, to not block the UI.
            try:
                # pylint: disable-msg=W0104
                self.payload.environments
                # pylint: disable-msg=W0104
                self.payload.groups
            except MetadataError:
                hubQ.send_message(self.__class__.__name__,
                                  _("No installation source available"))
                return

            # And then having done all that slow downloading, we need to do the first
            # refresh of the UI here so there's an environment selected by default.
            # This happens inside the main thread by necessity.  We can't do anything
            # that takes any real amount of time, or it'll block the UI from updating.
            if not self._first_refresh():
                return

        self.payload.release()

        hubQ.send_ready(self.__class__.__name__, False)

        # If packages were provided by an input kickstart file (or some other means),
        # we should do dependency solving here.
        self._apply()

    @gtk_action_wait
    def _first_refresh(self):
        try:
            self.refresh()
            return True
        except MetadataError:
            hubQ.send_message(self.__class__.__name__, _("No installation source available"))
            return False

    def refresh(self):
        NormalSpoke.refresh(self)

        threadMgr.wait(constants.THREAD_PAYLOAD_MD)

        self._environmentStore.clear()

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
                self.environment = environment
                sel = self.builder.get_object("environmentSelector")
                sel.select_iter(itr)

            firstEnvironment = False

        self.refreshAddons()

    def _addon_row_is_separator(self, model, itr, *args):
        # The last column of the model tells us if this row is a separator or not.
        return model[itr][3]

    def _addAddon(self, grp):
        (name, desc) = self.payload.groupDescription(grp)
        # If no groups are selected, select the default groups
        if not self._origEnvironment:
            selected = self.payload.environmentOptionIsDefault(self.environment, grp)
        else:
            selected = grp in self.selectedGroups

        self._addonStore.append([selected, "<b>%s</b>\n%s" % (name, desc), grp, False])

    def refreshAddons(self):
        self._addonStore.clear()
        if self.environment:
            # First, we make up two lists:  One of addons specific to this environment,
            # and one of all the others.  The environment-specific ones will be displayed
            # first and then a separator, and then the generic ones.  This is to make it
            # a little more obvious that the thing on the left side of the screen and the
            # thing on the right side of the screen are related.
            specific = []
            generic = []

            for grp in self.payload.groups:
                if self.payload.environmentHasOption(self.environment, grp):
                    specific.append(grp)
                elif self.payload._isGroupVisible(grp) and self.payload._groupHasInstallableMembers(grp):
                    generic.append(grp)

            for grp in specific:
                self._addAddon(grp)

            # This marks a separator in the view.
            self._addonStore.append([False, "", "", True])

            for grp in generic:
                self._addAddon(grp)

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
        itr = environmentView.get_selection().get_selected()[1]
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

    def on_environment_selection_changed(self, selection):
        (model, itr) = selection.get_selected()
        if not itr:
            return

        # Only do something if the row's not previously been selected.
        if not model[itr][0]:
            self.on_environment_toggled(None, model.get_path(itr))

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

    def on_addon_view_clicked(self, view, event, *args):
        if event and not event.type in [Gdk.EventType.BUTTON_RELEASE, Gdk.EventType.KEY_RELEASE]:
            return

        if event and event.type == Gdk.EventType.KEY_RELEASE and \
           event.keyval not in [Gdk.KEY_space, Gdk.KEY_Return, Gdk.KEY_ISO_Enter, Gdk.KEY_KP_Enter, Gdk.KEY_KP_Space]:
            return

        selection = view.get_selection()
        (model, itr) = selection.get_selected()
        if not itr:
            return

        # If the user clicked on the first column, they've clicked on the checkbox which was
        # handled separately from this signal handler.  Handling it again here will result in
        # the checkbox being toggled yet again.  So, we need to return in that case.
        col = view.get_cursor()[1]
        if not col or col.get_title() == "Selected":
            return

        # Always do something here, since addons can be toggled.
        self.on_addon_toggled(None, model.get_path(itr))

    def on_info_bar_clicked(self, *args):
        if not self._errorMsgs:
            return

        label = _("The following software marked for installation has errors.  "
                  "This is likely caused by an error with\nyour installation source.  "
                  "You can change your installation source or quit the installer.")
        dialog = DetailedErrorDialog(self.data, buttons=[_("_Quit"), _("_Cancel"),
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
            # Send the user to the installation source spoke.
            self.skipTo = "SourceSpoke"
            self.window.emit("button-clicked")
