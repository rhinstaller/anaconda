# The class for storage validation.
#
# Copyright (C) 2016  Red Hat, Inc.
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
# Author(s):  Vendula Poncova <vponcova@redhat.com>
#

import gi
gi.require_version("BlockDev", "2.0")
from gi.repository import BlockDev as blockdev

from blivet import arch
from blivet.errors import StorageError
from pykickstart.errors import KickstartParseError
from pykickstart.constants import CLEARPART_TYPE_ALL
from pyanaconda.i18n import N_, _
from pyanaconda.flags import flags
from pyanaconda.storage_utils import sanity_check, SanityError, SanityWarning
from pyanaconda.kickstart import doKickstartStorage, resetCustomStorageData
from pyanaconda.bootloader import BootLoaderError
from pyanaconda.threads import threadMgr, AnacondaThread
from pyanaconda.constants import THREAD_STORAGE, THREAD_STORAGE_WATCHER, THREAD_DASDFMT
from pyanaconda.ui.lib.disks import getDisks, applyDiskSelection
from pyanaconda.ui.validators import BaseValidator
from pyanaconda.ui.validators.hardware import HardwareValidator

import logging
log = logging.getLogger("anaconda")

__all__ = ["StorageValidator"]


class StorageValidator(BaseValidator):
    """A class to check and setup the storage."""

    title = N_("Storage validation")
    depends_on = [HardwareValidator]

    def __init__(self, config):
        super(StorageValidator, self).__init__(config)
        self._data = config.data
        self._storage = config.storage
        self._instclass = config.instclass

        # This list gets set up once in initialize and should not be modified
        # except perhaps to add advanced devices. It will remain the full list
        # of disks that can be included in the install.
        self.disks = []
        self.selected_disks = None

    def should_validate(self):
        return not flags.dirInstall

    def setup(self):
        # Prepare the storage
        self._storage_prepare()

        # Initialize the storage.
        threadMgr.add(AnacondaThread(name=THREAD_STORAGE_WATCHER,
                                     target=self._storage_initialize))

    def ready(self):
        # By default, the storage spoke is not ready.
        # We have to wait until storage initialization is done.
        return not (threadMgr.get(THREAD_STORAGE_WATCHER) or threadMgr.get(THREAD_DASDFMT))

    def _is_valid(self):
        return self._storage.root_device and not self.errors

    def _get_validation_error(self):
        """Return the validation error message."""
        if flags.automatedInstall and not self._storage.root_device:
            return _("The kickstart file is insufficient.")

        elif self._data.ignoredisk.onlyuse and self.errors:
            return _("Error checking storage configuration.")

        else:
            return _("An error has occurred.")

    def _storage_prepare(self):
        """Prepare devices in the setup."""

        if self._data.zerombr.zerombr and arch.is_s390():
            # if zerombr is specified in a ks file and there are unformatted
            # dasds, automatically format them. pass in storage.devicetree here
            # instead of storage.disks since media_present is checked on disks;
            # a dasd needing dasdfmt will fail this media check though
            to_format = [d for d in getDisks(self._storage.devicetree)
                         if d.type == "dasd" and blockdev.s390.dasd_needs_format(d.busid)]
            if to_format:
                self._run_dasdfmt(to_format)

    def _run_dasdfmt(self, to_format):
        """Generate the list of DASDs requiring dasdfmt and run dasdfmt
        against them.

        :param to_format: a list of disks to format
        :return: False if the formatting is not allowed, otherwise True
        """
        # If the storage thread is running, wait on it to complete before taking
        # any further actions on devices; most likely to occur if user has
        # zerombr in their ks file.
        threadMgr.wait(THREAD_STORAGE)

        # We cannot format if zerombr is not in ks file.
        if not self._data.zerombr.zerombr:
            log.warning("Unformatted DASDs cannot be used during installation.")
            return False

        # Format the disks.
        for disk in to_format:
            try:
                log.info("Formatting /dev/%s. This may take a moment.", disk.name)
                blockdev.s390.dasd_format(disk.name)
            except blockdev.S390Error as err:
                # Log errors if formatting fails, but don't halt the installer.
                self._report_error(str(err))
                continue

        return True

    def _storage_initialize(self):
        """Secondary initialize so wait for the storage thread to complete."""
        threadMgr.wait(THREAD_STORAGE)
        threadMgr.wait(THREAD_DASDFMT)

        self.disks = sorted(getDisks(self._storage.devicetree), key=lambda d: d.name)
        self.selected_disks = self._data.ignoredisk.onlyuse[:]

        # If only one disk is available, go ahead and mark it as selected.
        if len(self.disks) == 1:
            self._update_disk_list(self.disks[0])

        # If automated installation, then execute.
        if flags.automatedInstall:
            self._storage_execute()

    def _update_disk_list(self, disk):
        """Update self.selected_disks based on the selection."""
        # Get the name of the disk.
        name = disk.name
        # If the disk isn't already selected, select it.
        if name not in self.selected_disks:
            self.selected_disks.append(name)
        # If the disk is already selected, deselect it.
        elif name in self.selected_disks:
            self.selected_disks.remove(name)

    def _storage_execute(self):
        """Setup the storage."""
        try:
            log.info("Generating updated storage configuration")
            doKickstartStorage(self._storage, self._data, self._instclass)

        except (StorageError, KickstartParseError) as e:
            self._report_error(_("Storage configuration has failed: %s") % str(e))
            self._data.bootloader.bootDrive = ""
            self._data.clearpart.type = CLEARPART_TYPE_ALL
            self._data.clearpart.initAll = False
            self._storage.self._update(self._data)
            self._storage.autopart_type = self._data.autopart.type
            self._storage.reset()

            # now set ksdata back to the user's specified config
            applyDiskSelection(self._storage, self._data, self.selected_disks)

        except BootLoaderError as e:
            self._report_error(_("Boot loader setup has failed: %s") % str(e))
            self._data.bootloader.bootDrive = ""

        else:
            log.info("Checking storage configuration.")
            exns = sanity_check(self._storage)

            for exn in exns:
                if isinstance(exn, SanityError):
                    self._report_error(str(exn))

                elif isinstance(exn, SanityWarning):
                    log.warning(str(exn))
        finally:
            resetCustomStorageData(self._data)
