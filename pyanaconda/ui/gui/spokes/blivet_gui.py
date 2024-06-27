#
# Copyright (C) 2015 - 2017  Red Hat, Inc.
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
#                    Vojtech Trefny <vtrefny@redhat.com>
#

"""Module with the BlivetGuiSpoke class."""
from threading import Lock
from pyanaconda.errors import RemovedModuleError

try:
    from blivetgui.osinstall import BlivetGUIAnaconda  # pylint: disable=import-error
    from blivetgui.communication.client import BlivetGUIClient  # pylint: disable=import-error
    from blivetgui.config import config  # pylint: disable=import-error
except ImportError as e:
    raise RemovedModuleError(f"This module is not supported: {e}") from None

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.ui.gui.spokes import NormalSpoke
from pyanaconda.ui.helpers import StorageCheckHandler
from pyanaconda.ui.categories.system import SystemCategory
from pyanaconda.ui.gui.spokes.lib.summary import ActionSummaryDialog
from pyanaconda.core.constants import THREAD_EXECUTE_STORAGE, THREAD_STORAGE, \
    PARTITIONING_METHOD_BLIVET
from pyanaconda.core.i18n import _, CN_, C_
from pyanaconda.ui.lib.storage import create_partitioning, apply_partitioning
from pyanaconda.core.threads import thread_manager
from pyanaconda.modules.common.constants.services import STORAGE

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

log = get_module_logger(__name__)

# export only the spoke, no helper functions, classes or constants
__all__ = ["BlivetGuiSpoke"]


class BlivetGUIAnacondaClient(BlivetGUIClient):
    """The request handler for the Blivet-GUI."""

    def __init__(self):  # pylint: disable=super-init-not-called
        self.mutex = Lock()
        self._callback = None
        self._result = None

    def initialize(self, callback):
        """Initialize the client."""
        self._callback = callback

    def _send(self, data):
        """Send a message to a server."""
        self._result = bytes(self._callback(data))

    def _recv_msg(self):
        """Receive a message from a server."""
        return self._result

    def get_actions(self):
        """Get the current actions."""
        return self.remote_call("get_actions")


class BlivetGuiSpoke(NormalSpoke, StorageCheckHandler):
    ### class attributes defined by API ###

    # list all top-level objects from the .glade file that should be exposed
    # to the spoke or leave empty to extract everything
    builderObjects = ["blivetGuiSpokeWindow"]

    # the name of the main window widget
    mainWidgetName = "blivetGuiSpokeWindow"

    # name of the .glade file in the same directory as this source
    uiFile = "spokes/blivet_gui.glade"

    # category this spoke belongs to
    category = SystemCategory

    # title of the spoke (will be displayed on the hub)
    title = CN_("GUI|Spoke", "_Blivet-GUI Partitioning")

    @staticmethod
    def get_screen_id():
        """Return a unique id of this UI screen."""
        return "blivet-gui-partitioning"

    ### methods defined by API ###
    def __init__(self, data, storage, payload):
        """
        :see: pyanaconda.ui.common.Spoke.__init__
        :param data: data object passed to every spoke to load/store data
                     from/to it
        :type data: pykickstart.base.BaseHandler
        :param storage: object storing storage-related information
                        (disks, partitioning, bootloader, etc.)
        :type storage: blivet.Blivet
        :param payload: object storing payload-related information
        :type payload: pyanaconda.payload.Payload
        """
        self._error = None
        self._back_already_clicked = False
        self._label_actions = None
        self._button_reset = None
        self._button_undo = None

        self._client = None
        self._blivetgui = None
        self._partitioning = None
        self._device_tree = None

        self._storage_module = STORAGE.get_proxy()

        StorageCheckHandler.__init__(self)
        NormalSpoke.__init__(self, data, storage, payload)

    @property
    def label_actions(self):
        """The summary label.

        This property is required by Blivet-GUI.
        """
        return self._label_actions

    def initialize(self):
        """
        The initialize method that is called after the instance is created.
        The difference between __init__ and this method is that this may take
        a long time and thus could be called in a separated thread.

        :see: pyanaconda.ui.common.UIObject.initialize
        """
        NormalSpoke.initialize(self)
        self.initialize_start()

        config.log_dir = "/tmp"

        box = self.builder.get_object("BlivetGuiViewport")
        self._label_actions = self.builder.get_object("summary_label")
        self._button_reset = self.builder.get_object("resetAllButton")
        self._button_undo = self.builder.get_object("undoLastActionButton")

        self._client = BlivetGUIAnacondaClient()
        self._blivetgui = BlivetGUIAnaconda(self._client, self, box)

        # this needs to be done when the spoke is already "realized"
        self.entered.connect(self._blivetgui.ui_refresh)

        # set up keyboard shurtcuts for blivet-gui (and unset them after
        # user lefts the spoke)
        self.entered.connect(self._blivetgui.set_keyboard_shortcuts)
        self.exited.connect(self._blivetgui.unset_keyboard_shortcuts)

        self.initialize_done()

    def refresh(self):
        """
        The refresh method that is called every time the spoke is displayed.
        It should update the UI elements according to the contents of
        self.data.

        :see: pyanaconda.ui.common.UIObject.refresh
        """
        for thread_name in [THREAD_EXECUTE_STORAGE, THREAD_STORAGE]:
            thread_manager.wait(thread_name)

        if not self._partitioning:
            # Create the partitioning now. It cannot by done earlier, because
            # the storage spoke would use it as a default partitioning.
            self._partitioning = create_partitioning(PARTITIONING_METHOD_BLIVET)
            self._device_tree = STORAGE.get_proxy(self._partitioning.GetDeviceTree())

        self._back_already_clicked = False
        self._client.initialize(self._partitioning.SendRequest)
        self._blivetgui.initialize()

        # if we re-enter blivet-gui spoke, actions from previous visit were
        # not removed, we need to update number of blivet-gui actions
        self._blivetgui.set_actions(self._client.get_actions())

    def apply(self):
        """
        The apply method that is called when the spoke is left. It should
        update the contents of self.data with values set in the GUI elements.
        """
        pass

    @property
    def indirect(self):
        return True

    # This spoke has no status since it's not in a hub
    @property
    def status(self):
        return None

    def clear_errors(self):
        self._error = None
        self.clear_info()

    def _do_check(self):
        self.clear_errors()

        report = apply_partitioning(
            partitioning=self._partitioning,
            show_message_cb=log.debug,
            reset_storage_cb=self._reset_storage
        )

        StorageCheckHandler.errors = list(report.error_messages)
        StorageCheckHandler.warnings = list(report.warning_messages)

        if self.errors:
            self.set_warning(_("Error checking storage configuration.  <a href=\"\">Click for details</a> or press Done again to continue."))
        elif self.warnings:
            self.set_warning(_("Warning checking storage configuration.  <a href=\"\">Click for details</a> or press Done again to continue."))

        # on_info_bar_clicked requires self._error to be set, so set it to the
        # list of all errors and warnings that storage checking found.
        self._error = "\n".join(self.errors + self.warnings)

        return self._error == ""

    def activate_action_buttons(self, activate):
        self._button_undo.set_sensitive(activate)
        self._button_reset.set_sensitive(activate)

    ### handlers ###
    def on_info_bar_clicked(self, *args):
        log.debug("info bar clicked: %s (%s)", self._error, args)
        if not self._error:
            return

        dlg = Gtk.MessageDialog(flags=Gtk.DialogFlags.MODAL,
                                message_type=Gtk.MessageType.ERROR,
                                buttons=Gtk.ButtonsType.CLOSE,
                                message_format=str(self._error))
        dlg.set_decorated(False)

        with self.main_window.enlightbox(dlg):
            dlg.run()
            dlg.destroy()

    def on_back_clicked(self, button):
        # Clear any existing errors
        self.clear_errors()

        # If back has been clicked on once already and no other changes made on the screen,
        # run the storage check now.  This handles displaying any errors in the info bar.
        if not self._back_already_clicked:
            self._back_already_clicked = True

            # If we hit any errors while saving things above, stop and let the
            # user think about what they have done
            if self._error is not None:
                return

            if not self._do_check():
                return

        dialog = ActionSummaryDialog(self.data, self._device_tree)
        dialog.refresh()

        if dialog.actions:
            with self.main_window.enlightbox(dialog.window):
                rc = dialog.run()

            if rc != 1:
                # Cancel.  Stay on the blivet-gui screen.
                return

        NormalSpoke.on_back_clicked(self, button)

    def on_summary_button_clicked(self, _button):
        self._blivetgui.show_actions()

    def on_undo_action_button_clicked(self, _button):
        self._blivetgui.actions_undo()

    # This callback is for the button that just resets the UI to anaconda's
    # current understanding of the disk layout.
    def on_reset_button_clicked(self, *args):
        msg = _("Continuing with this action will reset all your partitioning selections "
                "to their current on-disk state.")

        dlg = Gtk.MessageDialog(flags=Gtk.DialogFlags.MODAL,
                                message_type=Gtk.MessageType.WARNING,
                                buttons=Gtk.ButtonsType.NONE,
                                message_format=msg)
        dlg.set_decorated(False)
        dlg.add_buttons(C_("GUI|Custom Partitioning|Reset Dialog", "_Reset selections"), 0,
                        C_("GUI|Custom Partitioning|Reset Dialog", "_Preserve current selections"), 1)
        dlg.set_default_response(1)

        with self.main_window.enlightbox(dlg):
            rc = dlg.run()
            dlg.destroy()

        if rc == 0:
            self._reset_storage()
            self.refresh()
            self._blivetgui.reload()

            # XXX: Reset currently preserves actions set in previous runs
            # of the spoke, so we need to 're-add' these to the ui
            self._blivetgui.set_actions(self._client.get_actions())

    def _reset_storage(self):
        # FIXME: Reset only the current partitioning module.
        self._storage_module.ResetPartitioning()
