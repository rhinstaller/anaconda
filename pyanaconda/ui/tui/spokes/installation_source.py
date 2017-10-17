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

from pyanaconda.flags import flags
from pyanaconda.ui.categories.software import SoftwareCategory
from pyanaconda.ui.tui.spokes import NormalTUISpoke
from pyanaconda.ui.tui.tuiobject import Dialog
from pyanaconda.threading import threadMgr, AnacondaThread
from pyanaconda.payload import PackagePayload, payloadMgr
from pyanaconda.i18n import N_, _, C_
from pyanaconda.image import opticalInstallMedia, potentialHdisoSources

from pyanaconda.constants import THREAD_SOURCE_WATCHER, THREAD_PAYLOAD
from pyanaconda.constants import THREAD_STORAGE_WATCHER
from pyanaconda.constants import THREAD_CHECK_SOFTWARE, ISO_DIR, DRACUT_ISODIR, DRACUT_REPODIR
from pyanaconda.constants import PAYLOAD_STATUS_PROBING_STORAGE

from pyanaconda.ui.helpers import SourceSwitchHandler

from simpleline.render.containers import ListColumnContainer
from simpleline.render.screen import InputState
from simpleline.render.screen_handler import ScreenHandler
from simpleline.render.widgets import TextWidget, EntryWidget

from blivet.util import get_mount_device, get_mount_paths

import os
import fnmatch

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["SourceSpoke"]


class SourceSpoke(NormalTUISpoke, SourceSwitchHandler):
    """ Spoke used to customize the install source repo.

       .. inheritance-diagram:: SourceSpoke
          :parts: 3
    """
    helpFile = "SourceSpoke.txt"
    category = SoftwareCategory

    SET_NETWORK_INSTALL_MODE = "network_install"

    def __init__(self, data, storage, payload, instclass):
        NormalTUISpoke.__init__(self, data, storage, payload, instclass)
        SourceSwitchHandler.__init__(self)
        self.title = N_("Installation source")
        self._container = None
        self._ready = False
        self._error = False
        self._cdrom = None

    def initialize(self):
        NormalTUISpoke.initialize(self)
        self.initialize_start()

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

        # report that the source spoke has been initialized
        self.initialize_done()

    def _payload_error(self):
        self._error = True

    def _repo_status(self):
        """ Return a string describing repo url or lack of one. """
        method = self.data.method
        if method.method == "url":
            return method.url or method.mirrorlist or method.metalink
        elif method.method == "nfs":
            return _("NFS server %s") % method.server
        elif method.method == "cdrom":
            return _("Local media")
        elif method.method == "harddrive":
            if not method.dir:
                return _("Error setting up software source")
            return os.path.basename(method.dir)
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
        NormalTUISpoke.refresh(self, args)

        threadMgr.wait(THREAD_PAYLOAD)

        self._container = ListColumnContainer(1, columns_width=78, spacing=1)

        if self.data.method.method == "harddrive" and \
           get_mount_device(DRACUT_ISODIR) == get_mount_device(DRACUT_REPODIR):
            message = _("The installation source is in use by the installer and cannot be changed.")
            self.window.add_with_separator(TextWidget(message))
            return

        if args == self.SET_NETWORK_INSTALL_MODE:
            self._container.add(TextWidget(_("Closest mirror")), self._set_network_close_mirror)
            self._container.add(TextWidget("http://"), self._set_network_url, SpecifyRepoSpoke.HTTP)
            self._container.add(TextWidget("https://"), self._set_network_url, SpecifyRepoSpoke.HTTPS)
            self._container.add(TextWidget("ftp://"), self._set_network_url, SpecifyRepoSpoke.FTP)
            self._container.add(TextWidget("nfs"), self._set_network_nfs)
        else:
            self.window.add(TextWidget(_("Choose an installation source type.")))
            self._container.add(TextWidget(_("CD/DVD")), self._set_cd_install_source)
            self._container.add(TextWidget(_("local ISO file")), self._set_iso_install_source)
            self._container.add(TextWidget(_("Network")), self._set_network_install_source)

        self.window.add_with_separator(self._container)

    # Set installation source callbacks

    def _set_cd_install_source(self, data):
        self.set_source_cdrom()
        self.payload.install_device = self._cdrom
        self.apply()
        self.close()

    def _set_iso_install_source(self, data):
        new_spoke = SelectDeviceSpoke(self.data,
                                      self.storage, self.payload,
                                      self.instclass)
        ScreenHandler.push_screen_modal(new_spoke)
        self.apply()
        self.close()

    def _set_network_install_source(self, data):
        ScreenHandler.replace_screen(self, self.SET_NETWORK_INSTALL_MODE)

    # Set network source callbacks

    def _set_network_close_mirror(self, data):
        self.set_source_closest_mirror()
        self.apply()
        self.close()

    def _set_network_url(self, data):
        new_spoke = SpecifyRepoSpoke(self.data, self.storage,
                                     self.payload, self.instclass, data)
        ScreenHandler.push_screen_modal(new_spoke)
        self.apply()
        self.close()

    def _set_network_nfs(self, data):
        self.set_source_nfs()
        new_spoke = SpecifyNFSRepoSpoke(self.data, self.storage,
                                        self.payload, self.instclass, self._error)
        ScreenHandler.push_screen_modal(new_spoke)
        self.apply()
        self.close()

    def input(self, args, key):
        """ Handle the input; this decides the repo source. """

        if not self._container.process_user_input(key):
            return super(SourceSpoke, self).input(args, key)

        return InputState.PROCESSED

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


class SpecifyRepoSpoke(NormalTUISpoke, SourceSwitchHandler):
    """ Specify the repo URL here if closest mirror not selected. """
    category = SoftwareCategory

    HTTP = 1
    HTTPS = 2
    FTP = 3

    def __init__(self, data, storage, payload, instclass, protocol):
        NormalTUISpoke.__init__(self, data, storage, payload, instclass)
        SourceSwitchHandler.__init__(self)
        self.title = N_("Specify Repo Options")
        self.protocol = protocol
        self._container = None

        self._url = self.data.url.url

    def refresh(self, args=None):
        """ Refresh window. """
        NormalTUISpoke.refresh(self, args)

        self._container = ListColumnContainer(1)

        dialog = Dialog(_("Repo URL"))
        self._container.add(EntryWidget(dialog.title, self.data.method.url), self._set_repo_url, dialog)

        self.window.add_with_separator(self._container)

    def _set_repo_url(self, dialog):
        self._url = dialog.run()

    def input(self, args, key):
        if self._container.process_user_input(key):
            self.apply()
            self.redraw()
            return InputState.PROCESSED
        else:
            return NormalTUISpoke.input(self, args, key)

    @property
    def indirect(self):
        return True

    def apply(self):
        """ Apply all of our changes. """
        if self.protocol == SpecifyRepoSpoke.HTTP and not self._url.startswith("http://"):
            url = "http://" + self._url
        elif self.protocol == SpecifyRepoSpoke.HTTPS and not self._url.startswith("https://"):
            url = "https://" + self._url
        elif self.protocol == SpecifyRepoSpoke.FTP and not self._url.startswith("ftp://"):
            url = "ftp://" + self._url
        else:
            # protocol either unknown or entry already starts with a protocol
            # specification
            url = self._url
        self.set_source_url(url)


class SpecifyNFSRepoSpoke(NormalTUISpoke, SourceSwitchHandler):
    """ Specify server and mount opts here if NFS selected. """
    category = SoftwareCategory

    def __init__(self, data, storage, payload, instclass, error):
        NormalTUISpoke.__init__(self, data, storage, payload, instclass)
        SourceSwitchHandler.__init__(self)
        self.title = N_("Specify Repo Options")
        self._container = None
        self._error = error

        nfs = self.data.method

        self._nfs_opts = ""
        self._nfs_server = ""

        if nfs.method == "nfs" and (nfs.server and nfs.dir):
            self._nfs_server = "%s:%s" % (nfs.server, nfs.dir)
            self._nfs_opts = nfs.opts

    def refresh(self, args=None):
        """ Refresh window. """
        NormalTUISpoke.refresh(self, args)

        self._container = ListColumnContainer(1)

        dialog = Dialog(title=_("SERVER:/PATH"), conditions=[self._check_nfs_server])
        self._container.add(EntryWidget(dialog.title, self._nfs_server), self._set_nfs_server, dialog)

        dialog = Dialog(title=_("NFS mount options"))
        self._container.add(EntryWidget(dialog.title, self._nfs_opts), self._set_nfs_opts, dialog)

        self.window.add_with_separator(self._container)

    def _set_nfs_server(self, dialog):
        self._nfs_server = dialog.run()

    def _check_nfs_server(self, user_input, report_func):
        if ":" not in user_input or len(user_input.split(":")) != 2:
            report_func(_("Server must be specified as SERVER:/PATH"))
            return False

        return True

    def _set_nfs_opts(self, dialog):
        self._nfs_opts = dialog.run()

    def input(self, args, key):
        if self._container.process_user_input(key):
            self.apply()
            self.redraw()
            return InputState.PROCESSED
        else:
            return NormalTUISpoke.input(self, args, key)

    @property
    def indirect(self):
        return True

    def apply(self):
        """ Apply our changes. """
        if self._nfs_server == "" or ':' not in self._nfs_server:
            return False

        if self._nfs_server.startswith("nfs://"):
            self._nfs_server = self._nfs_server[6:]

        try:
            (self.data.method.server, self.data.method.dir) = self._nfs_server.split(":", 2)
        except ValueError as err:
            log.error("ValueError: %s", err)
            self._error = True
            return

        opts = self._nfs_opts or ""
        self.set_source_nfs(opts)


class SelectDeviceSpoke(NormalTUISpoke):
    """ Select device containing the install source ISO file. """
    category = SoftwareCategory

    def __init__(self, data, storage, payload, instclass):
        NormalTUISpoke.__init__(self, data, storage, payload, instclass)
        self.title = N_("Select device containing the ISO file")
        self._container = None
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

        self._container = ListColumnContainer(1, columns_width=78, spacing=1)

        # check if the storage refresh thread is running
        if threadMgr.get(THREAD_STORAGE_WATCHER):
            # storage refresh is running - just report it
            # so that the user can refresh until it is done
            # TODO: refresh once the thread is done ?
            message = _(PAYLOAD_STATUS_PROBING_STORAGE)
            self.window.add_with_separator(TextWidget(message))

        # check if there are any mountable devices
        if self._mountable_devices:
            for d in self._mountable_devices:
                self._container.add(TextWidget(d[1]), callback=self._select_mountable_device, data=d[0])

            self.window.add_with_separator(self._container)

        else:
            message = _("No mountable devices found")
            self.window.add_with_separator(TextWidget(message))

    def _select_mountable_device(self, data):
        self._device = data
        new_spoke = SelectISOSpoke(self.data,
                                   self.storage, self.payload,
                                   self.instclass, self._device)
        ScreenHandler.push_screen_modal(new_spoke)
        self.close()

    def input(self, args, key):
        if self._container.process_user_input(key):
            return InputState.PROCESSED
        else:
            # either the input was not a number or
            # we don't have the disk for the given number
            return super(SelectDeviceSpoke, self).input(args, key)

    # Override Spoke.apply
    def apply(self):
        pass


class SelectISOSpoke(NormalTUISpoke, SourceSwitchHandler):
    """ Select an ISO to use as install source. """
    category = SoftwareCategory

    def __init__(self, data, storage, payload, instclass, device):
        NormalTUISpoke.__init__(self, data, storage, payload, instclass)
        SourceSwitchHandler.__init__(self)
        self.title = N_("Select an ISO to use as install source")
        self._container = None
        self.args = self.data.method
        self._device = device
        self._mount_device()
        self._isos = self._getISOs()

    def refresh(self, args=None):
        NormalTUISpoke.refresh(self, args)

        if self._isos:
            self._container = ListColumnContainer(1, columns_width=78, spacing=1)

            for iso in self._isos:
                self._container.add(TextWidget(iso), callback=self._select_iso_callback, data=iso)

            self.window.add_with_separator(self._container)
        else:
            message = _("No *.iso files found in device root folder")
            self.window.add_with_separator(TextWidget(message))

    def _select_iso_callback(self, data):
        self._current_iso_path = data
        self.apply()
        self.close()

    def input(self, args, key):
        if self._container is not None and self._container.process_user_input(key):
            return InputState.PROCESSED
        # TRANSLATORS: 'c' to continue
        elif key.lower() == C_('TUI|Spoke Navigation', 'c'):
            self.apply()
            self.close()
            return InputState.PROCESSED
        else:
            return super(SelectISOSpoke, self).input(args, key)

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
            # If a hdd iso source has already been selected previously we need
            # to clear it now.
            # Otherwise we would get a crash if the same iso was selected again
            # as _unmount_device() would try to unmount a partition that is in use
            # due to the payload still holding on to the ISO file.
            if self.data.method.method == "harddrive":
                self.unset_source()
            self.set_source_hdd_iso(self._device, self._current_iso_path)
        # unmount the device - the payload will remount it anyway
        # (if it uses it)
        self._unmount_device()
