# Storage configuration spoke dialogs
#
# Copyright (C) 2011-2020  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import constants
from pyanaconda.core.constants import PAYLOAD_LIVE_TYPES
from pyanaconda.core.i18n import _
from pyanaconda.core.timer import Timer
from pyanaconda.product import productName
from pyanaconda.threading import threadMgr
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.utils import escape_markup

log = get_module_logger(__name__)

__all__ = ["NeedSpaceDialog", "NoSpaceDialog", "RESPONSE_CANCEL", "RESPONSE_OK",
           "RESPONSE_MODIFY_SW", "RESPONSE_RECLAIM", "RESPONSE_QUIT", "DASD_FORMAT_NO_CHANGE",
           "DASD_FORMAT_REFRESH", "DASD_FORMAT_RETURN_TO_HUB"]

# Response ID codes for all the various buttons on all the dialogs.
RESPONSE_CANCEL = 0
RESPONSE_OK = 1
RESPONSE_MODIFY_SW = 2
RESPONSE_RECLAIM = 3
RESPONSE_QUIT = 4
DASD_FORMAT_NO_CHANGE = -1
DASD_FORMAT_REFRESH = 1
DASD_FORMAT_RETURN_TO_HUB = 2


class InstallOptionsDialogBase(GUIObject):
    uiFile = "spokes/lib/storage_dialogs.glade"

    def __init__(self, *args, **kwargs):
        self.payload = kwargs.pop("payload", None)
        super().__init__(*args, **kwargs)
        self._grabObjects()

    def _grabObjects(self):
        pass

    def run(self):
        rc = self.window.run()
        self.window.destroy()
        return rc

    def _modify_sw_link_clicked(self, label, uri):
        if self._software_is_ready():
            self.window.response(RESPONSE_MODIFY_SW)

        return True

    def _get_sw_needs_text(self, required_space, sw_space, auto_swap):
        tooltip = _("Please wait... software metadata still loading.")

        if self.payload.type in PAYLOAD_LIVE_TYPES:
            sw_text = (_("Your current <b>%(product)s</b> software "
                         "selection requires <b>%(total)s</b> of available "
                         "space, including <b>%(software)s</b> for software and "
                         "<b>%(swap)s</b> for swap space.")
                       % {"product": escape_markup(productName),
                          "total": escape_markup(str(required_space)),
                          "software": escape_markup(str(sw_space)),
                          "swap": escape_markup(str(auto_swap))})
        else:
            sw_text = (_("Your current <a href=\"\" title=\"%(tooltip)s\"><b>%(product)s</b> software "
                         "selection</a> requires <b>%(total)s</b> of available "
                         "space, including <b>%(software)s</b> for software and "
                         "<b>%(swap)s</b> for swap space.")
                       % {"tooltip": escape_markup(tooltip),
                          "product": escape_markup(productName),
                          "total": escape_markup(str(required_space)),
                          "software": escape_markup(str(sw_space)),
                          "swap": escape_markup(str(auto_swap))})
        return sw_text

    # Methods to handle sensitivity of the modify button.
    def _software_is_ready(self):
        # FIXME:  Would be nicer to just ask the spoke if it's ready.
        return (not threadMgr.get(constants.THREAD_PAYLOAD) and
                not threadMgr.get(constants.THREAD_SOFTWARE_WATCHER) and
                not threadMgr.get(constants.THREAD_CHECK_SOFTWARE) and
                self.payload.is_ready())

    def _check_for_storage_thread(self, button):
        if self._software_is_ready():
            button.set_has_tooltip(False)

            # False means this function should never be called again.
            return False
        else:
            return True

    def _add_modify_watcher(self, widget):
        # If the payload fetching thread is still running, the user can't go to
        # modify the software selection screen.  Thus, we have to set the button
        # insensitive and wait until software selection is ready to go.
        if not self._software_is_ready():
            Timer().timeout_sec(1, self._check_for_storage_thread, widget)


class NeedSpaceDialog(InstallOptionsDialogBase):
    builderObjects = ["need_space_dialog"]
    mainWidgetName = "need_space_dialog"

    def _grabObjects(self):
        self.disk_free_label = self.builder.get_object("need_space_disk_free_label")
        self.fs_free_label = self.builder.get_object("need_space_fs_free_label")

    def _set_free_space_labels(self, disk_free, fs_free):
        self.disk_free_label.set_text(str(disk_free))
        self.fs_free_label.set_text(str(fs_free))

    # pylint: disable=arguments-differ
    def refresh(self, required_space, sw_space, auto_swap, disk_free, fs_free):
        sw_text = self._get_sw_needs_text(required_space, sw_space, auto_swap)
        label_text = _("%s The disks you've selected have the following "
                       "amounts of free space:") % sw_text
        label = self.builder.get_object("need_space_desc_label")
        label.set_markup(label_text)

        if self.payload.type not in PAYLOAD_LIVE_TYPES:
            label.connect("activate-link", self._modify_sw_link_clicked)

        self._set_free_space_labels(disk_free, fs_free)

        label_text = _("<b>You don't have enough space available to install "
                       "%s</b>.  You can shrink or remove existing partitions "
                       "via our guided reclaim space tool, or you can adjust your "
                       "partitions on your own in the custom partitioning "
                       "interface.") % escape_markup(productName)
        self.builder.get_object("need_space_options_label").set_markup(label_text)
        self._add_modify_watcher(label)


class NoSpaceDialog(InstallOptionsDialogBase):
    builderObjects = ["no_space_dialog"]
    mainWidgetName = "no_space_dialog"

    def _grabObjects(self):
        self.disk_free_label = self.builder.get_object("no_space_disk_free_label")
        self.fs_free_label = self.builder.get_object("no_space_fs_free_label")

    def _set_free_space_labels(self, disk_free, fs_free):
        self.disk_free_label.set_text(str(disk_free))
        self.fs_free_label.set_text(str(fs_free))

    # pylint: disable=arguments-differ
    def refresh(self, required_space, sw_space, auto_swap, disk_free, fs_free):
        label_text = self._get_sw_needs_text(required_space, sw_space, auto_swap)
        label_text += (_("  You don't have enough space available to install "
                         "<b>%(product)s</b>, even if you used all of the free space "
                         "available on the selected disks.")
                       % {"product": escape_markup(productName)})
        label = self.builder.get_object("no_space_desc_label")
        label.set_markup(label_text)

        if self.payload.type not in PAYLOAD_LIVE_TYPES:
            label.connect("activate-link", self._modify_sw_link_clicked)

        self._set_free_space_labels(disk_free, fs_free)

        label_text = _("<b>You don't have enough space available to install "
                       "%(productName)s</b>, even if you used all of the free space "
                       "available on the selected disks.  You could add more "
                       "disks for additional space, "
                       "modify your software selection to install a smaller "
                       "version of <b>%(productName)s</b>, or quit the installer.") % \
                               {"productName": escape_markup(productName)}
        self.builder.get_object("no_space_options_label").set_markup(label_text)

        self._add_modify_watcher(label)
