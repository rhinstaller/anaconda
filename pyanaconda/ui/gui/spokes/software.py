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

from gi.repository import Gtk, Pango

from pyanaconda.flags import flags
from pyanaconda.i18n import _, C_, CN_
from pyanaconda.packaging import PackagePayload, payloadMgr
from pyanaconda.threads import threadMgr, AnacondaThread
from pyanaconda import constants, iutil

from pyanaconda.ui.communication import hubQ
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.gui.spokes.lib.detailederror import DetailedErrorDialog
from pyanaconda.ui.gui.utils import blockedHandler, gtk_action_wait, escape_markup
from pyanaconda.ui.categories.software import SoftwareCategory

import logging
log = logging.getLogger("anaconda")

import sys, copy

__all__ = ["SoftwareSelectionSpoke"]

class SoftwareSelectionSpoke(NormalSpoke):
    builderObjects = ["addonStore", "environmentStore", "softwareWindow"]
    mainWidgetName = "softwareWindow"
    uiFile = "spokes/software.glade"
    helpFile = "SoftwareSpoke.xml"

    category = SoftwareCategory

    icon = "package-x-generic-symbolic"
    title = CN_("GUI|Spoke", "_SOFTWARE SELECTION")

    # Add-on selection states
    # no user interaction with this add-on
    _ADDON_DEFAULT = 0
    # user selected
    _ADDON_SELECTED = 1
    # user de-selected
    _ADDON_DESELECTED = 2

    def __init__(self, *args, **kwargs):
        NormalSpoke.__init__(self, *args, **kwargs)
        self._errorMsgs = None
        self._tx_id = None
        self._selectFlag = False

        self.selectedGroups = []
        self.excludedGroups = []
        self.environment = None

        self._environmentListBox = self.builder.get_object("environmentListBox")
        self._addonListBox = self.builder.get_object("addonListBox")

        # Connect viewport scrolling with listbox focus events
        environmentViewport = self.builder.get_object("environmentViewport")
        addonViewport = self.builder.get_object("addonViewport")
        self._environmentListBox.set_focus_vadjustment(environmentViewport.get_vadjustment())
        self._addonListBox.set_focus_vadjustment(addonViewport.get_vadjustment())

        # Used to store how the user has interacted with add-ons for the default add-on
        # selection logic. The dictionary keys are group IDs, and the values are selection
        # state constants. See refreshAddons for how the values are used.
        self._addonStates = {}

        # Used for detecting whether anything's changed in the spoke.
        self._origAddons = []
        self._origEnvironment = None

        # Register event listeners to update our status on payload events
        payloadMgr.addListener(payloadMgr.STATE_PACKAGE_MD, self._downloading_package_md)
        payloadMgr.addListener(payloadMgr.STATE_GROUP_MD, self._downloading_group_md)
        payloadMgr.addListener(payloadMgr.STATE_FINISHED, self._payload_finished)
        payloadMgr.addListener(payloadMgr.STATE_ERROR, self._payload_error)

    # Payload event handlers
    def _downloading_package_md(self):
        hubQ.send_message(self.__class__.__name__, _("Downloading package metadata..."))

    def _downloading_group_md(self):
        hubQ.send_message(self.__class__.__name__, _("Downloading group metadata..."))

    def _payload_finished(self):
        self.environment = self.data.packages.environment

    def _payload_error(self):
        hubQ.send_message(self.__class__.__name__, payloadMgr.error)

    def _apply(self):
        env = self._get_selected_environment()
        if not env:
            return

        # Not a kickstart with packages, setup the environment and groups
        if not (flags.automatedInstall and self.data.packages.seen):
            addons = self._get_selected_addons()
            for group in addons:
                if group not in self.selectedGroups:
                    self.selectedGroups.append(group)

            self._selectFlag = False
            self.payload.data.packages.groupList = []
            self.payload.selectEnvironment(env)
            self.environment = env
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
        processingDone = bool(not threadMgr.get(constants.THREAD_CHECK_SOFTWARE) and
                              not threadMgr.get(constants.THREAD_PAYLOAD) and
                              not self._errorMsgs and self.txid_valid)

        # we should always check processingDone before checking the other variables,
        # as they might be inconsistent until processing is finished
        if flags.automatedInstall:
            return processingDone and self.data.packages.seen
        else:
            return processingDone and self._get_selected_environment() is not None

    @property
    def changed(self):
        env = self._get_selected_environment()
        if not env:
            return True

        addons = self._get_selected_addons()

        # Don't redo dep solving if nothing's changed.
        if env == self._origEnvironment and set(addons) == set(self._origAddons) and \
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

        return bool(not threadMgr.get(constants.THREAD_SOFTWARE_WATCHER) and
                    not threadMgr.get(constants.THREAD_PAYLOAD) and
                    not threadMgr.get(constants.THREAD_CHECK_SOFTWARE) and
                    self.payload.baseRepo is not None)

    @property
    def showable(self):
        return isinstance(self.payload, PackagePayload)

    @property
    def status(self):
        if self._errorMsgs:
            return _("Error checking software selection")

        if not self.ready:
            return _("Installation source not set up")

        if not self.txid_valid:
            return _("Source changed - please verify")

        env = self._get_selected_environment()
        if not env:
            # Kickstart installs with %packages will have a row selected, unless
            # they did an install without a desktop environment.  This should
            # catch that one case.
            if flags.automatedInstall and self.data.packages.seen:
                return _("Custom software selected")

            return _("Nothing selected")

        return self.payload.environmentDescription(env)[0]

    def initialize(self):
        NormalSpoke.initialize(self)
        threadMgr.add(AnacondaThread(name=constants.THREAD_SOFTWARE_WATCHER,
                      target=self._initialize))

    def _initialize(self):
        threadMgr.wait(constants.THREAD_PAYLOAD)

        if not flags.automatedInstall or not self.data.packages.seen:
            # having done all the slow downloading, we need to do the first refresh
            # of the UI here so there's an environment selected by default.  This
            # happens inside the main thread by necessity.  We can't do anything
            # that takes any real amount of time, or it'll block the UI from
            # updating.
            if not self._first_refresh():
                return

        hubQ.send_ready(self.__class__.__name__, False)

        # If packages were provided by an input kickstart file (or some other means),
        # we should do dependency solving here.
        self._apply()

    def _parseEnvironments(self):
        # Set all of the add-on selection states to the default
        self._addonStates = {}
        for grp in self.payload.groups:
            self._addonStates[grp] = self._ADDON_DEFAULT

    @gtk_action_wait
    def _first_refresh(self):
        self.refresh()
        return True

    def _add_row(self, listbox, name, desc, button, clicked):
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        button.set_valign(Gtk.Align.START)
        button.connect("toggled", clicked, row)
        box.add(button)

        label = Gtk.Label(label="<b>%s</b>\n%s" % (escape_markup(name), escape_markup(desc)),
                          use_markup=True, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                          hexpand=True, xalign=0, yalign=0.5)
        box.add(label)

        row.add(box)
        listbox.insert(row, -1)

    def refresh(self):
        NormalSpoke.refresh(self)

        threadMgr.wait(constants.THREAD_PAYLOAD)

        if self.environment not in self.payload.environments:
            self.environment = None

        # If no environment is selected, use the default from the instclass.
        # If nothing is set in the instclass, the first environment will be
        # selected below.
        if not self.environment and self.payload.instclass and \
                self.payload.instclass.defaultPackageEnvironment in self.payload.environments:
            self.environment = self.payload.instclass.defaultPackageEnvironment

        firstEnvironment = True
        firstRadio = None

        self._clear_listbox(self._environmentListBox)

        for environment in self.payload.environments:
            (name, desc) = self.payload.environmentDescription(environment)

            radio = Gtk.RadioButton(group=firstRadio)

            # automatically select an environment if this is an interactive install
            active = environment == self.environment or \
                     not flags.automatedInstall and not self.environment and firstEnvironment
            radio.set_active(active)
            if active:
                self.environment = environment

            self._add_row(self._environmentListBox, name, desc, radio,
                    self.on_radio_button_toggled)
            firstRadio = firstRadio or radio

            firstEnvironment = False

        self.refreshAddons()
        self._environmentListBox.show_all()
        self._addonListBox.show_all()

    def _addAddon(self, grp):
        (name, desc) = self.payload.groupDescription(grp)

        if grp in self._addonStates:
            # If the add-on was previously selected by the user, select it
            if self._addonStates[grp] == self._ADDON_SELECTED:
                selected = True
            # If the add-on was previously de-selected by the user, de-select it
            elif self._addonStates[grp] == self._ADDON_DESELECTED:
                selected = False
            # Otherwise, use the default state
            else:
                selected = self.payload.environmentOptionIsDefault(self.environment, grp)
        else:
            selected = self.payload.environmentOptionIsDefault(self.environment, grp)

        check = Gtk.CheckButton()
        check.set_active(selected)
        self._add_row(self._addonListBox, name, desc, check, self.on_checkbox_toggled)

    @property
    def _addSep(self):
        """ Whether the addon list contains a separator. """
        return len(self.payload.environmentAddons[self.environment][0]) > 0 and \
                len(self.payload.environmentAddons[self.environment][1]) > 0

    def refreshAddons(self):
        if self.environment and (self.environment in self.payload.environmentAddons):
            self._clear_listbox(self._addonListBox)

            # We have two lists:  One of addons specific to this environment,
            # and one of all the others.  The environment-specific ones will be displayed
            # first and then a separator, and then the generic ones.  This is to make it
            # a little more obvious that the thing on the left side of the screen and the
            # thing on the right side of the screen are related.
            #
            # If a particular add-on was previously selected or de-selected by the user, that
            # state will be used. Otherwise, the add-on will be selected if it is a default
            # for this environment.

            for grp in self.payload.environmentAddons[self.environment][0]:
                self._addAddon(grp)

            # This marks a separator in the view - only add it if there's both environment
            # specific and generic addons.
            if self._addSep:
                self._addonListBox.insert(Gtk.Separator(), -1)

            for grp in self.payload.environmentAddons[self.environment][1]:
                self._addAddon(grp)

        self._selectFlag = True

        if self._errorMsgs:
            self.set_warning(_("Error checking software dependencies.  Click for details."))
        else:
            self.clear_info()

    def _allAddons(self):
        addons = copy.copy(self.payload.environmentAddons[self.environment][0])
        if self._addSep:
            addons.append('')
        addons += self.payload.environmentAddons[self.environment][1]
        return addons

    def _get_selected_addons(self):
        retval = []

        addons = self._allAddons()

        for (ndx, row) in enumerate(self._addonListBox.get_children()):
            box = row.get_children()[0]

            if isinstance(box, Gtk.Separator):
                continue

            button = box.get_children()[0]
            if button.get_active():
                retval.append(addons[ndx])

        return retval

    def _get_selected_environment(self):
        # Returns the currently selected environment (self.environment
        # is set in both initilize() and apply(), so we don't need to
        # care about the state of the internal data model at all)
        return self.environment

    def _clear_listbox(self, listbox):
        for child in listbox.get_children():
            listbox.remove(child)
            del(child)

    @property
    def txid_valid(self):
        return self._tx_id == self.payload.txID

    # Signal handlers
    def on_checkbox_toggled(self, button, row):
        row.activate()

    def on_radio_button_toggled(self, radio, row):
        # If the radio button toggled to inactive, don't reactivate the row
        if not radio.get_active():
            return
        row.activate()

    def on_environment_activated(self, listbox, row):
        if not self._selectFlag:
            return

        box = row.get_children()[0]
        button = box.get_children()[0]

        with blockedHandler(button, self.on_radio_button_toggled):
            button.set_active(True)

        # Remove all the groups that were selected by the previously
        # selected environment.
        if self.environment:
            for groupid in self.payload.environmentGroups(self.environment):
                if groupid in self.selectedGroups:
                    self.selectedGroups.remove(groupid)

        # Then mark the clicked environment as selected and update the screen.
        self.environment = self.payload.environments[row.get_index()]
        self.refreshAddons()
        self._addonListBox.show_all()

    def on_addon_activated(self, listbox, row):
        box = row.get_children()[0]
        if isinstance(box, Gtk.Separator):
            return

        button = box.get_children()[0]
        addons = self._allAddons()
        group = addons[row.get_index()]

        wasActive = group in self.selectedGroups

        with blockedHandler(button, self.on_checkbox_toggled):
            button.set_active(not wasActive)

        if wasActive:
            self.selectedGroups.remove(group)
            self._addonStates[group] = self._ADDON_DESELECTED
        else:
            self.selectedGroups.append(group)

            if group in self.excludedGroups:
                self.excludedGroups.remove(group)

            self._addonStates[group] = self._ADDON_SELECTED

    def on_info_bar_clicked(self, *args):
        if not self._errorMsgs:
            return

        label = _("The software marked for installation has the following errors.  "
                  "This is likely caused by an error with your installation source.  "
                  "You can quit the installer, change your software source, or change "
                  "your software selections.")
        dialog = DetailedErrorDialog(self.data,
                buttons=[C_("GUI|Software Selection|Error Dialog", "_Quit"),
                         C_("GUI|Software Selection|Error Dialog", "_Modify Software Source"),
                         C_("GUI|Software Selection|Error Dialog", "Modify _Selections")],
                label=label)
        with self.main_window.enlightbox(dialog.window):
            dialog.refresh(self._errorMsgs)
            rc = dialog.run()

        dialog.window.destroy()

        if rc == 0:
            # Quit.
            iutil.ipmi_report(constants.IPMI_ABORTED)
            sys.exit(0)
        elif rc == 1:
            # Send the user to the installation source spoke.
            self.skipTo = "SourceSpoke"
            self.window.emit("button-clicked")
        elif rc == 2:
            # Close the dialog so the user can change selections.
            pass
        else:
            pass
