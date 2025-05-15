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
import fnmatch
import os

from simpleline.render.containers import ListColumnContainer
from simpleline.render.prompt import Prompt
from simpleline.render.screen import InputState
from simpleline.render.screen_handler import ScreenHandler
from simpleline.render.widgets import EntryWidget, TextWidget

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import (
    DRACUT_ISODIR,
    ISO_DIR,
    PAYLOAD_STATUS_PROBING_STORAGE,
    PAYLOAD_TYPE_DNF,
    SOURCE_TYPE_HMC,
    SOURCE_TYPE_NFS,
    SOURCE_TYPE_URL,
    THREAD_CHECK_SOFTWARE,
    THREAD_PAYLOAD,
    THREAD_SOURCE_WATCHER,
    THREAD_STORAGE_WATCHER,
)
from pyanaconda.core.i18n import N_, _
from pyanaconda.core.payload import parse_nfs_url
from pyanaconda.flags import flags
from pyanaconda.modules.common.constants.objects import DEVICE_TREE
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.structures.payload import RepoConfigurationData
from pyanaconda.payload import utils as payload_utils
from pyanaconda.payload.image import (
    find_potential_hdiso_sources,
    get_hdiso_source_description,
    get_hdiso_source_info,
)
from pyanaconda.payload.manager import PayloadState, payloadMgr
from pyanaconda.payload.utils import get_device_path
from pyanaconda.threading import AnacondaThread, threadMgr
from pyanaconda.ui.categories.software import SoftwareCategory
from pyanaconda.ui.context import context
from pyanaconda.ui.helpers import SourceSwitchHandler
from pyanaconda.ui.tui.spokes import NormalTUISpoke
from pyanaconda.ui.tui.tuiobject import Dialog

log = get_module_logger(__name__)

__all__ = ["SourceSpoke"]


class SourceSpoke(NormalTUISpoke, SourceSwitchHandler):
    """ Spoke used to customize the install source repo.

       .. inheritance-diagram:: SourceSpoke
          :parts: 3
    """
    category = SoftwareCategory

    SET_NETWORK_INSTALL_MODE = "network_install"

    @staticmethod
    def get_screen_id():
        """Return a unique id of this UI screen."""
        return "software-source-configuration"

    @classmethod
    def should_run(cls, environment, data):
        """Don't run for any non-package payload."""
        if not NormalTUISpoke.should_run(environment, data):
            return False

        return context.payload_type == PAYLOAD_TYPE_DNF

    def __init__(self, data, storage, payload):
        NormalTUISpoke.__init__(self, data, storage, payload)
        SourceSwitchHandler.__init__(self)
        self.title = N_("Installation source")
        self._container = None
        self._ready = False
        self._error = False
        self._hmc = False

    def initialize(self):
        NormalTUISpoke.initialize(self)
        self.initialize_start()

        threadMgr.add(AnacondaThread(name=THREAD_SOURCE_WATCHER,
                                     target=self._initialize))
        payloadMgr.add_listener(PayloadState.ERROR, self._payload_error)

    def _initialize(self):
        """ Private initialize. """
        threadMgr.wait(THREAD_PAYLOAD)

        # Enable the SE/HMC option.
        if self.payload.source_type == SOURCE_TYPE_HMC:
            self._hmc = True

        self._ready = True

        # report that the source spoke has been initialized
        self.initialize_done()

    def _payload_error(self):
        self._error = True

    @property
    def status(self):
        if self._error:
            return _("Error setting up software source")
        elif not self.ready:
            return _("Processing...")
        elif not self.payload.is_complete():
            return _("Nothing selected")
        else:
            source_proxy = self.payload.get_source_proxy()
            return source_proxy.Description

    @property
    def completed(self):
        if flags.automatedInstall and self.ready and not self.payload.base_repo:
            return False

        return not self._error and self.ready and self.payload.is_complete()

    def refresh(self, args=None):
        NormalTUISpoke.refresh(self, args)
        threadMgr.wait(THREAD_PAYLOAD)

        self._container = ListColumnContainer(1, columns_width=78, spacing=1)

        if args == self.SET_NETWORK_INSTALL_MODE:
            if conf.payload.enable_closest_mirror:
                self._container.add(TextWidget(_("Closest mirror")),
                                    self._set_network_close_mirror)

            self._container.add(TextWidget("http://"),
                                self._set_network_url,
                                SpecifyRepoSpoke.HTTP)
            self._container.add(TextWidget("https://"),
                                self._set_network_url,
                                SpecifyRepoSpoke.HTTPS)
            self._container.add(TextWidget("ftp://"),
                                self._set_network_url,
                                SpecifyRepoSpoke.FTP)
            self._container.add(TextWidget("nfs"),
                                self._set_network_nfs)
        else:
            self.window.add(TextWidget(_("Choose an installation source type.")))
            self._container.add(TextWidget(_("CD/DVD")), self._set_cd_install_source)
            self._container.add(TextWidget(_("local ISO file")), self._set_iso_install_source)
            self._container.add(TextWidget(_("Network")), self._set_network_install_source)

            if self._hmc:
                self._container.add(TextWidget(_("SE/HMC")), self._set_hmc_install_source)

        self.window.add_with_separator(self._container)

    # Set installation source callbacks

    def _set_cd_install_source(self, data):
        self.set_source_cdrom()
        self.apply()
        self.close()

    def _set_hmc_install_source(self, data):
        self.set_source_hmc()
        self.apply()
        self.close()

    def _set_iso_install_source(self, data):
        new_spoke = SelectDeviceSpoke(self.data, self.storage, self.payload)
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
        new_spoke = SpecifyRepoSpoke(self.data, self.storage, self.payload, data)
        ScreenHandler.push_screen_modal(new_spoke)
        self.apply()
        self.close()

    def _set_network_nfs(self, data):
        new_spoke = SpecifyNFSRepoSpoke(self.data, self.storage, self.payload, self._error)
        ScreenHandler.push_screen_modal(new_spoke)
        self.apply()
        self.close()

    def input(self, args, key):
        """ Handle the input; this decides the repo source. """
        if not self._container.process_user_input(key):
            return super().input(args, key)

        return InputState.PROCESSED

    @property
    def ready(self):
        """ Check if the spoke is ready. """
        return (self._ready and
                not threadMgr.get(THREAD_PAYLOAD) and
                not threadMgr.get(THREAD_CHECK_SOFTWARE))

    def apply(self):
        """ Execute the selections made. """
        # if we had any errors, e.g. from a previous attempt to set the source,
        # clear them at this point
        self._error = False

        payloadMgr.restart_thread(self.payload, checkmount=False)


class SpecifyRepoSpoke(NormalTUISpoke, SourceSwitchHandler):
    """ Specify the repo URL here if closest mirror not selected. """
    category = SoftwareCategory

    HTTP = 1
    HTTPS = 2
    FTP = 3

    def __init__(self, data, storage, payload, protocol):
        NormalTUISpoke.__init__(self, data, storage, payload)
        SourceSwitchHandler.__init__(self)
        self.title = N_("Specify Repo Options")
        self.protocol = protocol
        self._container = None
        self._url = self._get_url()

    def _get_url(self):
        """Get the URL of the current source."""
        source_proxy = self.payload.get_source_proxy()

        if source_proxy.Type == SOURCE_TYPE_URL:
            repo_configuration = RepoConfigurationData.from_structure(
                source_proxy.RepoConfiguration
            )

            return repo_configuration.url

        return ""

    def refresh(self, args=None):
        """ Refresh window. """
        NormalTUISpoke.refresh(self, args)

        self._container = ListColumnContainer(1)

        dialog = Dialog(_("Repo URL"))
        self._container.add(EntryWidget(dialog.title, self._url), self._set_repo_url, dialog)

        self.window.add_with_separator(self._container)

    def _set_repo_url(self, dialog):
        self._url = dialog.run()

    def input(self, args, key):
        if self._container.process_user_input(key):
            self.apply()
            return InputState.PROCESSED_AND_REDRAW
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

    def __init__(self, data, storage, payload, error):
        NormalTUISpoke.__init__(self, data, storage, payload)
        SourceSwitchHandler.__init__(self)
        self.title = N_("Specify Repo Options")
        self._container = None
        self._error = error

        options, host, path = self._get_nfs()
        self._nfs_opts = options
        self._nfs_server = "{}:{}".format(host, path) if host else ""

    def _get_nfs(self):
        """Get the NFS options, host and path of the current source."""
        source_proxy = self.payload.get_source_proxy()

        if source_proxy.Type == SOURCE_TYPE_NFS:
            return parse_nfs_url(source_proxy.URL)

        return "", "", ""

    def refresh(self, args=None):
        """ Refresh window. """
        NormalTUISpoke.refresh(self, args)

        self._container = ListColumnContainer(1)

        dialog = Dialog(title=_("SERVER:/PATH"), conditions=[self._check_nfs_server])
        self._container.add(EntryWidget(dialog.title, self._nfs_server),
                            self._set_nfs_server, dialog)

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
            return InputState.PROCESSED_AND_REDRAW
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
            (server, directory) = self._nfs_server.split(":", 2)
        except ValueError as err:
            log.error("ValueError: %s", err)
            self._error = True
            return

        opts = self._nfs_opts or ""
        self.set_source_nfs(server, directory, opts)


class SelectDeviceSpoke(NormalTUISpoke):
    """ Select device containing the install source ISO file. """
    category = SoftwareCategory

    def __init__(self, data, storage, payload):
        super().__init__(data, storage, payload)
        self.title = N_("Select device containing the ISO file")
        self._container = None
        self._device_tree = STORAGE.get_proxy(DEVICE_TREE)
        self._mountable_devices = self._get_mountable_devices()
        self._device = None

    @property
    def indirect(self):
        return True

    def _get_mountable_devices(self):
        disks = []

        for device_name in find_potential_hdiso_sources():
            device_info = get_hdiso_source_info(self._device_tree, device_name)
            device_desc = get_hdiso_source_description(device_info)
            disks.append([device_name, device_desc])

        return disks

    def refresh(self, args=None):
        super().refresh(args)

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
                self._container.add(TextWidget(d[1]),
                                    callback=self._select_mountable_device,
                                    data=d[0])

            self.window.add_with_separator(self._container)

        else:
            message = _("No mountable devices found")
            self.window.add_with_separator(TextWidget(message))

    def _select_mountable_device(self, data):
        self._device = data
        new_spoke = SelectISOSpoke(self.data, self.storage, self.payload, self._device)
        ScreenHandler.push_screen_modal(new_spoke)
        self.close()

    def input(self, args, key):
        if self._container.process_user_input(key):
            return InputState.PROCESSED
        else:
            # either the input was not a number or
            # we don't have the disk for the given number
            return super().input(args, key)

    # Override Spoke.apply
    def apply(self):
        pass


class SelectISOSpoke(NormalTUISpoke, SourceSwitchHandler):
    """ Select an ISO to use as install source. """
    category = SoftwareCategory

    def __init__(self, data, storage, payload, device):
        NormalTUISpoke.__init__(self, data, storage, payload)
        SourceSwitchHandler.__init__(self)
        self.title = N_("Select an ISO to use as install source")
        self._container = None
        self._device = device
        self._isos = self._collect_iso_files()

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
        elif key.lower() == Prompt.CONTINUE:
            self.apply()
            return InputState.PROCESSED_AND_CLOSE
        else:
            return super().input(args, key)

    @property
    def indirect(self):
        return True

    def _collect_iso_files(self):
        """Collect *.iso files."""
        try:
            self._mount_device()
            return self._getISOs()
        finally:
            self._unmount_device()

    def _mount_device(self):
        """ Mount the device so we can search it for ISOs. """
        # FIXME: Use a unique mount point.
        device_path = get_device_path(self._device)
        mounts = payload_utils.get_mount_paths(device_path)

        # We have to check both ISO_DIR and the DRACUT_ISODIR because we
        # still reference both, even though /mnt/install is a symlink to
        # /run/install.  Finding mount points doesn't handle the symlink
        if ISO_DIR not in mounts and DRACUT_ISODIR not in mounts:
            # We're not mounted to either location, so do the mount
            payload_utils.mount_device(self._device, ISO_DIR)

    def _unmount_device(self):
        # FIXME: Unmount a specific mount point.
        payload_utils.unmount_device(self._device, mount_point=None)

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
