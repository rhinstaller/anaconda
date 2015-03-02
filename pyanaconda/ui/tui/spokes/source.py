# Source repo text spoke
#
# Copyright (C) 2013  Red Hat, Inc.
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
# Red Hat Author(s): Samantha N. Bueno <sbueno@redhat.com>
#

from pyanaconda.flags import flags
from pyanaconda.ui.categories.software import SoftwareCategory
from pyanaconda.ui.tui.spokes import EditTUISpoke, NormalTUISpoke
from pyanaconda.ui.tui.spokes import EditTUISpokeEntry as Entry
from pyanaconda.ui.tui.simpleline import TextWidget, ColumnWidget
from pyanaconda.threads import threadMgr, AnacondaThread
from pyanaconda.packaging import PackagePayload, payloadMgr
from pyanaconda.i18n import N_, _
from pyanaconda.image import opticalInstallMedia, potentialHdisoSources
from pyanaconda.iutil import DataHolder

from pyanaconda.constants import THREAD_SOURCE_WATCHER, THREAD_PAYLOAD
from pyanaconda.constants import THREAD_STORAGE_WATCHER
from pyanaconda.constants import THREAD_CHECK_SOFTWARE, ISO_DIR, DRACUT_ISODIR, DRACUT_REPODIR
from pyanaconda.constants_text import INPUT_PROCESSED

from pyanaconda.ui.helpers import SourceSwitchHandler

from blivet.util import get_mount_device, get_mount_paths

import re
import os
import fnmatch

import logging
LOG = logging.getLogger("anaconda")


__all__ = ["SourceSpoke"]

class SourceSpoke(EditTUISpoke, SourceSwitchHandler):
    """ Spoke used to customize the install source repo. """
    title = N_("Installation source")
    category = SoftwareCategory

    _protocols = (N_("Closest mirror"), "http://", "https://", "ftp://", "nfs")

    # default to 'closest mirror', as done in the GUI
    _selection = 1

    def __init__(self, app, data, storage, payload, instclass):
        EditTUISpoke.__init__(self, app, data, storage, payload, instclass)
        SourceSwitchHandler.__init__(self)
        self._ready = False
        self._error = False
        self._cdrom = None

    def initialize(self):
        EditTUISpoke.initialize(self)

        threadMgr.add(AnacondaThread(name=THREAD_SOURCE_WATCHER,
                                     target=self._initialize))
        payloadMgr.addListener(payloadMgr.STATE_ERROR, self._payload_error)

    def _initialize(self):
        """ Private initialize. """
        threadMgr.wait(THREAD_PAYLOAD)
        # If we've previously set up to use a CD/DVD method, the media has
        # already been mounted by payload.setup.  We can't try to mount it
        # again.  So just use what we already know to create the selector.
        # Otherwise, check to see if there's anything available.
        if self.data.method.method == "cdrom":
            self._cdrom = self.payload.install_device
        elif not flags.automatedInstall:
            self._cdrom = opticalInstallMedia(self.storage.devicetree)

        self._ready = True

    def _payload_error(self):
        self._error = True

    def _repo_status(self):
        """ Return a string describing repo url or lack of one. """
        if self.data.method.method == "url":
            return self.data.method.url or self.data.method.mirrorlist
        elif self.data.method.method == "nfs":
            return _("NFS server %s") % self.data.method.server
        elif self.data.method.method == "cdrom":
            return _("Local media")
        elif self.data.method.method == "harddrive":
            if not self.data.method.dir:
                return _("Error setting up software source")
            return os.path.basename(self.data.method.dir)
        elif self.payload.baseRepo:
            return _("Closest mirror")
        else:
            return _("Nothing selected")

    @property
    def showable(self):
        return isinstance(self.payload, PackagePayload)

    @property
    def status(self):
        if self._error:
            return _("Error setting up software source")
        elif not self.ready:
            return _("Processing...")
        else:
            return self._repo_status()

    @property
    def completed(self):
        if flags.automatedInstall and self.ready and not self.payload.baseRepo:
            return False
        else:
            return not self._error and self.ready and (self.data.method.method or self.payload.baseRepo)

    def refresh(self, args=None):
        EditTUISpoke.refresh(self, args)

        threadMgr.wait(THREAD_PAYLOAD)

        _methods = [_("CD/DVD"), _("local ISO file"), _("Network")]

        if self.data.method.method == "harddrive" and \
           get_mount_device(DRACUT_ISODIR) == get_mount_device(DRACUT_REPODIR):
            message = _("The installation source is in use by the installer and cannot be changed.")
            self._window += [TextWidget(message), ""]
            return True

        if args == 3:
            text = [TextWidget(_(p)) for p in self._protocols]
        else:
            self._window += [TextWidget(_("Choose an installation source type."))]
            text = [TextWidget(m) for m in _methods]

        def _prep(i, w):
            """ Mangle our text to make it look pretty on screen. """
            number = TextWidget("%2d)" % (i + 1))
            return ColumnWidget([(4, [number]), (None, [w])], 1)

        # gnarl and mangle all of our widgets so things look pretty on screen
        choices = [_prep(i, w) for i, w in enumerate(text)]

        displayed = ColumnWidget([(78, choices)], 1)
        self._window.append(displayed)

        return True

    def input(self, args, key):
        """ Handle the input; this decides the repo source. """
        try:
            num = int(key)
        except ValueError:
            return key

        if args == 3:
            # network install
            self._selection = num
            if self._selection == 1:
                # closest mirror
                self.set_source_closest_mirror()
                self.apply()
                self.close()
                return INPUT_PROCESSED
            elif self._selection in range(2, 5):
                # preliminary URL source switch
                self.set_source_url()
                newspoke = SpecifyRepoSpoke(self.app, self.data, self.storage,
                                          self.payload, self.instclass, self._selection)
                self.app.switch_screen_modal(newspoke)
                self.apply()
                self.close()
                return INPUT_PROCESSED
            elif self._selection == 5:
                # nfs
                # preliminary NFS source switch
                self.set_source_nfs()
                newspoke = SpecifyNFSRepoSpoke(self.app, self.data, self.storage,
                                        self.payload, self.instclass, self._selection, self._error)
                self.app.switch_screen_modal(newspoke)
                self.apply()
                self.close()
                return INPUT_PROCESSED
        elif num == 2:
            # local ISO file (HDD ISO)
            self._selection = num
            newspoke = SelectDeviceSpoke(self.app, self.data,
                    self.storage, self.payload,
                    self.instclass)
            self.app.switch_screen_modal(newspoke)
            self.apply()
            self.close()
            return INPUT_PROCESSED
        else:
            # mounted ISO
            if num == 1:
                # iso selected, just set some vars and return to main hub
                self.set_source_cdrom()
                self.payload.install_device = self._cdrom
                self.apply()
                self.close()
                return INPUT_PROCESSED
            else:
                self.app.switch_screen(self, num)
        return INPUT_PROCESSED

    @property
    def ready(self):
        """ Check if the spoke is ready. """
        return (self._ready and
                not threadMgr.get(THREAD_PAYLOAD) and
                not threadMgr.get(THREAD_CHECK_SOFTWARE))

    def apply(self):
        """ Execute the selections made. """
        # If askmethod was provided on the command line, entering the source
        # spoke wipes that out.
        if flags.askmethod:
            flags.askmethod = False

        # if we had any errors, e.g. from a previous attempt to set the source,
        # clear them at this point
        self._error = False

        payloadMgr.restartThread(self.storage, self.data, self.payload, self.instclass,
                checkmount=False)

class SpecifyRepoSpoke(EditTUISpoke, SourceSwitchHandler):
    """ Specify the repo URL here if closest mirror not selected. """
    title = N_("Specify Repo Options")
    category = SoftwareCategory

    edit_fields = [
        Entry(N_("Repo URL"), "url", re.compile(".*$"), True)
        ]

    def __init__(self, app, data, storage, payload, instclass, selection):
        EditTUISpoke.__init__(self, app, data, storage, payload, instclass)
        SourceSwitchHandler.__init__(self)
        self.selection = selection
        self.args = self.data.method

    def refresh(self, args=None):
        """ Refresh window. """
        return EditTUISpoke.refresh(self, args)

    @property
    def indirect(self):
        return True

    def apply(self):
        """ Apply all of our changes. """
        url = None
        if self.selection == 2 and not self.args.url.startswith("http://"):
            url = "http://" + self.args.url
        elif self.selection == 3 and not self.args.url.startswith("https://"):
            url = "https://" + self.args.url
        elif self.selection == 4 and not self.args.url.startswith("ftp://"):
            url = "ftp://" + self.args.url
        else:
            # protocol either unknown or entry already starts with a protocol
            # specification
            url = self.args.url
        self.set_source_url(url)

class SpecifyNFSRepoSpoke(EditTUISpoke, SourceSwitchHandler):
    """ Specify server and mount opts here if NFS selected. """
    title = N_("Specify Repo Options")
    category = SoftwareCategory

    edit_fields = [
        Entry(N_("<server>:/<path>"), "server", re.compile(".*$"), True),
        Entry(N_("NFS mount options"), "opts", re.compile(".*$"), True)
    ]

    def __init__(self, app, data, storage, payload, instclass, selection, error):
        EditTUISpoke.__init__(self, app, data, storage, payload, instclass)
        SourceSwitchHandler.__init__(self)
        self.selection = selection
        self._error = error

        nfs = self.data.method
        self.args = DataHolder(server="", opts=nfs.opts or "")
        if nfs.method == "nfs" and nfs.server and nfs.dir:
            self.args.server = "%s:%s" % (nfs.server, nfs.dir)

    def refresh(self, args=None):
        """ Refresh window. """
        return EditTUISpoke.refresh(self, args)

    @property
    def indirect(self):
        return True

    def apply(self):
        """ Apply our changes. """
        if self.args.server == "" or not ':' in self.args.server:
            return False

        if self.args.server.startswith("nfs://"):
            self.args.server = self.args.server[6:]

        try:
            (self.data.method.server, self.data.method.dir) = self.args.server.split(":", 2)
        except ValueError as err:
            LOG.error("ValueError: %s", err)
            self._error = True
            return

        opts = self.args.opts or ""
        self.set_source_nfs(opts)

class SelectDeviceSpoke(NormalTUISpoke):
    """ Select device containing the install source ISO file. """
    title = N_("Select device containing the ISO file")
    category = SoftwareCategory

    def __init__(self, app, data, storage, payload, instclass):
        NormalTUISpoke.__init__(self, app, data, storage, payload, instclass)
        self._currentISOFile = None
        self._mountable_devices = self._get_mountable_devices()
        self._device = None

    @property
    def indirect(self):
        return True

    def _sanitize_model(self, model):
        return model.replace("_", " ")

    def _get_mountable_devices(self):
        disks = []
        fstring = "%(model)s %(path)s (%(size)s MB) %(format)s %(label)s"
        for dev in potentialHdisoSources(self.storage.devicetree):
            # path model size format type uuid of format
            dev_info = {"model": self._sanitize_model(dev.disk.model),
                        "path": dev.path,
                        "size": dev.size,
                        "format": dev.format.name or "",
                        "label": dev.format.label or dev.format.uuid or ""
                        }
            disks.append([dev, fstring % dev_info])
        return disks

    def refresh(self, args=None):
        NormalTUISpoke.refresh(self, args)

        # check if the storage refresh thread is running
        if threadMgr.get(THREAD_STORAGE_WATCHER):
            # storage refresh is running - just report it
            # so that the user can refresh until it is done
            # TODO: refresh once the thread is done ?
            message = _("Probing storage...")
            self._window += [TextWidget(message), ""]
            return True

        # check if there are any mountable devices
        if self._mountable_devices:
            def _prep(i, w):
                """ Mangle our text to make it look pretty on screen. """
                number = TextWidget("%2d)" % (i + 1))
                return ColumnWidget([(4, [number]), (None, [w])], 1)

            devices = [TextWidget(d[1]) for d in self._mountable_devices]

            # gnarl and mangle all of our widgets so things look pretty on
            # screen
            choices = [_prep(i, w) for i, w in enumerate(devices)]

            displayed = ColumnWidget([(78, choices)], 1)
            self._window.append(displayed)

        else:
            message = _("No mountable devices found")
            self._window += [TextWidget(message), ""]
        return True

    def input(self, args, key):
        try:
            # try to switch to one of the mountable devices
            # to look for ISOs
            num = int(key)
            device = self._mountable_devices[num-1][0]  # get the device object
            self._device = device
            newspoke = SelectISOSpoke(self.app, self.data,
                                      self.storage, self.payload,
                                      self.instclass, device)
            self.app.switch_screen_modal(newspoke)
            self.close()
            return True
        except (IndexError, ValueError):
            # either the input was not a number or
            # we don't have the disk for the given number
            return key

    # Override Spoke.apply
    def apply(self):
        pass

class SelectISOSpoke(NormalTUISpoke, SourceSwitchHandler):
    """ Select an ISO to use as install source. """
    title = N_("Select an ISO to use as install source")
    category = SoftwareCategory

    def __init__(self, app, data, storage, payload, instclass, device):
        NormalTUISpoke.__init__(self, app, data, storage, payload, instclass)
        SourceSwitchHandler.__init__(self)
        self.selection = None
        self.args = self.data.method
        self._device = device
        self._mount_device()
        self._isos = self._getISOs()

    def refresh(self, args=None):
        NormalTUISpoke.refresh(self, args)

        if self._isos:
            isos = [TextWidget(iso) for iso in self._isos]

            def _prep(i, w):
                """ Mangle our text to make it look pretty on screen. """
                number = TextWidget("%2d)" % (i + 1))
                return ColumnWidget([(4, [number]), (None, [w])], 1)

            # gnarl and mangle all of our widgets so things look pretty on screen
            choices = [_prep(i, w) for i, w in enumerate(isos)]

            displayed = ColumnWidget([(78, choices)], 1)
            self._window.append(displayed)
        else:
            message = _("No *.iso files found in device root folder")
            self._window += [TextWidget(message), ""]

        return True

    def input(self, args, key):
        if key == "c":
            self.apply()
            self.close()
            return key
        try:
            num = int(key)
            # get the ISO path
            self._current_iso_path = self._isos[num-1]
            self.apply()
            self.close()
            return True
        except (IndexError, ValueError):
            return key

    @property
    def indirect(self):
        return True

    def _mount_device(self):
        """ Mount the device so we can search it for ISOs. """
        mounts = get_mount_paths(self._device.path)
        # We have to check both ISO_DIR and the DRACUT_ISODIR because we
        # still reference both, even though /mnt/install is a symlink to
        # /run/install.  Finding mount points doesn't handle the symlink
        if ISO_DIR not in mounts and DRACUT_ISODIR not in mounts:
            # We're not mounted to either location, so do the mount
            self._device.format.mount(mountpoint=ISO_DIR)

    def _unmount_device(self):
        self._device.format.unmount()

    def _getISOs(self):
        """List all *.iso files in the root folder
        of the currently selected device.

        TODO: advanced ISO file selection
        :returns: a list of *.iso file paths
        :rtype: list
        """
        isos = []
        for filename in os.listdir(ISO_DIR):
            if fnmatch.fnmatch(filename.lower(), "*.iso"):
                isos.append(filename)
        return isos

    def apply(self):
        """ Apply all of our changes. """

        if self._current_iso_path:
            self.set_source_hdd_iso(self._device, self._current_iso_path)
        # unmount the device - the (YUM) payload will remount it anyway
        # (if it uses it)
        self._unmount_device()
