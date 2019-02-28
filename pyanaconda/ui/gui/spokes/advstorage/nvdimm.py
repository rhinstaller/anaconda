# NVDIMM configuration dialog
#
# Copyright (C) 2018  Red Hat, Inc.
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

from pyanaconda import constants
from pyanaconda.threads import threadMgr, AnacondaThread
from pyanaconda.ui.gui import GUIObject
from pyanaconda.ui.gui.utils import gtk_action_nowait
from pyanaconda.storage_utils import try_populate_devicetree, \
    nvdimm_update_ksdata_after_reconfiguration
from pykickstart.constants import NVDIMM_MODE_SECTOR

from pyanaconda.i18n import _, CN_

import logging
log = logging.getLogger("anaconda")

DEFAULT_SECTOR_SIZE = 512

__all__ = ["NVDIMMDialog"]

PAGE_ACTION = 1
PAGE_RESULT_ERROR = 2
PAGE_RESULT_SUCCESS = 3

NVDIMM_SECTOR_SIZE_OPTIONS = ['512', '4096']


class NVDIMMDialog(GUIObject):
    """
       .. inheritance-diagram:: NVDIMMDialog
          :parts: 3
    """
    builderObjects = ["nvdimmDialog", "sectorSizeAdjustment"]
    mainWidgetName = "nvdimmDialog"
    uiFile = "spokes/advstorage/nvdimm.glade"

    def __init__(self, data, storage, namespaces):
        GUIObject.__init__(self, data)

        self.namespaces = namespaces
        self.storage = storage
        self.nvdimm = self.storage.nvdimm()

        self._error = None
        self._update_devicetree = False

        self._startButton = self.builder.get_object("startButton")
        self._infoLabel = self.builder.get_object("infoLabel")
        self._devicesLabel = self.builder.get_object("devicesLabel")
        self._cancelButton = self.builder.get_object("cancelButton")
        self._okButton = self.builder.get_object("okButton")
        self._reconfigureSpinner = self.builder.get_object("reconfigureSpinner")
        self._repopulateSpinner = self.builder.get_object("repopulateSpinner")
        self._repopulateLabel = self.builder.get_object("repopulateLabel")
        self._sectorSizeLabel = self.builder.get_object("sectorSizeLabel")
        self._sectorSizeCombo = self.builder.get_object("sectorSizeCombo")
        self._conditionNotebook = self.builder.get_object("conditionNotebook")
        self._setup_size_combo()

    def _setup_size_combo(self):
        for size in NVDIMM_SECTOR_SIZE_OPTIONS:
            self._sectorSizeCombo.append_text(size)

    def refresh(self):
        self._sectorSizeCombo.set_active(0)
        if self.namespaces:
            self._devicesLabel.set_text("%s" % ", ".join(self.namespaces))
        else:
            msg = CN_("GUI|Advanced Storage|NVDIM", "No device to be reconfigured selected.")
            self._infoLabel.set_text(msg)
            for widget in [self._sectorSizeCombo, self._okButton, self._startButton,
                           self._sectorSizeLabel]:
                widget.set_sensitive(False)

    def run(self):
        rc = self.window.run()
        self.window.destroy()
        return rc

    @property
    def sector_size(self):
        return int(self._sectorSizeCombo.get_active_text())

    def on_start_clicked(self, *args):
        self._conditionNotebook.set_current_page(PAGE_ACTION)

        for widget in [self._startButton, self._cancelButton, self._sectorSizeCombo,
                       self._okButton]:
            widget.set_sensitive(False)

        self._reconfigureSpinner.start()

        threadMgr.add(AnacondaThread(name=constants.THREAD_NVDIMM_RECONFIGURE, target=self._reconfigure,
                                     args=(self.namespaces, NVDIMM_MODE_SECTOR, self.sector_size)))

    def _reconfigure(self, namespaces, mode, sector_size):
        for namespace in namespaces:
            if namespace in self.nvdimm.namespaces:
                log.info("nvdimm: reconfiguring %s to %s mode", namespace, mode)
                try:
                    self.nvdimm.reconfigure_namespace(namespace, mode, sector_size=sector_size)
                    self._update_devicetree = True
                except Exception as e:  # pylint: disable=broad-except
                    self._error = "%s: %s" % (namespace, str(e))
                    log.error("nvdimm: reconfiguring %s to %s mode error: %s",
                              namespace, mode, e)
                    break
                # Update kickstart data for generated ks
                nvdimm_update_ksdata_after_reconfiguration(self.data,
                                                           namespace,
                                                           mode=mode,
                                                           sectorsize=sector_size)
            else:
                log.error("nvdimm: namespace %s to be reconfigured not found", namespace)
        self._after_reconfigure()

    @gtk_action_nowait
    def _after_reconfigure(self):
        # When reconfiguration is done, update the UI.  We don't need to worry
        # about the user escaping from the dialog because all the buttons are
        # marked insensitive.
        self._reconfigureSpinner.stop()

        if self._error:
            self.builder.get_object("deviceErrorLabel").set_text(self._error)
            self._error = None
            self._conditionNotebook.set_current_page(PAGE_RESULT_ERROR)
            self._okButton.set_sensitive(True)
        else:
            self._conditionNotebook.set_current_page(PAGE_RESULT_SUCCESS)
            if self._update_devicetree:
                self._repopulateSpinner.start()
                threadMgr.add(AnacondaThread(name=constants.THREAD_NVDIMM_REPOPULATE, target=self._repopulate))

    def _repopulate(self):
        log.info("nvdimm: repopulating device tree")
        self.storage.devicetree.reset()
        try_populate_devicetree(self.storage.devicetree)
        self._after_repopulate()

    @gtk_action_nowait
    def _after_repopulate(self):
        self._repopulateSpinner.stop()
        self._repopulateLabel.set_text(_("Rescanning disks finished."))
        self._okButton.set_sensitive(True)
