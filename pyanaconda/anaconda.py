# anaconda: The Red Hat Linux Installation program
#
# Copyright (C) 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007
# Red Hat, Inc.  All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import os
import sys
import stat
from glob import glob
from tempfile import mkstemp
import threading

from pyanaconda import addons
from pyanaconda.bootloader import get_bootloader
from pyanaconda.core.constants import DisplayModes
from pyanaconda.core import util, constants
from pyanaconda.dbus.launcher import AnacondaDBusLauncher
from pyanaconda.modules.common.constants.objects import AUTO_PARTITIONING
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.payload.source import SourceFactory, PayloadSourceTypeUnrecognized

from pyanaconda.anaconda_loggers import get_stdout_logger
stdoutLog = get_stdout_logger()

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class Anaconda(object):
    def __init__(self):
        from pyanaconda import desktop

        self._bootloader = None
        self.desktop = desktop.Desktop()
        self.dir = None
        self._display_mode = None
        self._interactive_mode = True
        self.gui_startup_failed = False
        self.id = None
        self._instClass = None
        self._intf = None
        self.isHeadless = False
        self.ksdata = None
        self.methodstr = None
        self.additional_repos = None
        self.opts = None
        self._payload = None
        self.proxy = None
        self.decorated = False

        self.stage2 = None
        self._storage = None
        self.updateSrc = None
        self.mehConfig = None

        # *sigh* we still need to be able to write this out
        self.xdriver = None

        # Data for inhibiting the screensaver
        self.dbus_session_connection = None
        self.dbus_inhibit_id = None

        # This is used to synchronize Gtk.main calls between the graphical
        # interface and error dialogs. Whoever gets to their initialization code
        # first will lock gui_initializing
        self.gui_initialized = threading.Lock()

        # Create class for launching our dbus session
        self._dbus_launcher = None

    def set_from_opts(self, opts):
        """Load argument to variables from self.opts."""
        self.opts = opts
        self.decorated = opts.decorated
        self.proxy = opts.proxy
        self.updateSrc = opts.updateSrc
        self.methodstr = opts.method
        self.stage2 = opts.stage2
        self.additional_repos = opts.addRepo

    @property
    def dbus_launcher(self):
        if not self._dbus_launcher:
            self._dbus_launcher = AnacondaDBusLauncher()

        return self._dbus_launcher

    @property
    def bootloader(self):
        if not self._bootloader:
            self._bootloader = get_bootloader()

        return self._bootloader

    @property
    def instClass(self):
        if not self._instClass:
            from pyanaconda.installclass import factory

            # Get install class by name.
            if self.ksdata.anaconda.installclass.seen:
                name = self.ksdata.anaconda.installclass.name
                self._instClass = factory.get_install_class_by_name(name)
            # Or just find the best one.
            else:
                self._instClass = factory.get_best_install_class()

        return self._instClass

    def _getInterface(self):
        return self._intf

    def _setInterface(self, v):
        # "lambda cannot contain assignment"
        self._intf = v

    def _delInterface(self):
        del self._intf

    intf = property(_getInterface, _setInterface, _delInterface)

    @property
    def payload(self):
        # Try to find the payload class.  First try the install
        # class.  If it doesn't give us one, fall back to the default.
        if not self._payload:
            from pyanaconda.flags import flags

            if self.ksdata.ostreesetup.seen:
                from pyanaconda.payload.rpmostreepayload import RPMOSTreePayload
                klass = RPMOSTreePayload
            elif flags.livecdInstall:
                from pyanaconda.payload.livepayload import LiveImagePayload
                klass = LiveImagePayload
            elif self.ksdata.method.method == "liveimg":
                from pyanaconda.payload.livepayload import LiveImageKSPayload
                klass = LiveImageKSPayload
            else:
                from pyanaconda.payload.dnfpayload import DNFPayload
                klass = DNFPayload

            self._payload = klass(self.ksdata)

        return self._payload

    @property
    def protected(self):
        specs = []
        if os.path.exists("/run/initramfs/livedev") and \
           stat.S_ISBLK(os.stat("/run/initramfs/livedev")[stat.ST_MODE]):
            specs.append(os.readlink("/run/initramfs/livedev"))

        # methodstr and stage2 become strings in ways that pylint can't figure out
        # pylint: disable=unsubscriptable-object
        if self.methodstr and SourceFactory.is_harddrive(self.methodstr):
            specs.append(self.methodstr[3:].split(":", 3)[0])

        if self.stage2 and SourceFactory.is_harddrive(self.stage2):
            specs.append(self.stage2[3:].split(":", 3)[0])

        for additional_repo in self.additional_repos:
            _name, repo_url = self._get_additional_repo_name(additional_repo)
            if SourceFactory.is_harddrive(repo_url):
                specs.append(repo_url[3:].split(":", 3)[0])

        # zRAM swap devices need to be protected
        for zram_dev in glob("/dev/zram*"):
            specs.append(zram_dev)

        return specs

    @staticmethod
    def _get_additional_repo_name(repo):
        name, rest = repo.split(',', maxsplit=1)
        return name, rest

    @property
    def storage(self):
        if not self._storage:
            from pyanaconda.storage.osinstall import InstallerStorage
            import blivet.arch

            self._storage = InstallerStorage(ksdata=self.ksdata)
            self._set_default_fstype(self._storage)

            if blivet.arch.is_s390():
                self._load_plugin_s390()

        return self._storage

    @property
    def display_mode(self):
        return self._display_mode

    @display_mode.setter
    def display_mode(self, new_mode):
        if isinstance(new_mode, DisplayModes):
            if self._display_mode:
                old_mode = self._display_mode
                log.debug("changing display mode from %s to %s",
                          old_mode.value, new_mode.value)
            else:
                log.debug("setting display mode to %s", new_mode.value)
            self._display_mode = new_mode
        else:  # unknown mode name - ignore & log an error
            log.error("tried to set an unknown display mode name: %s", new_mode.value)

    @property
    def interactive_mode(self):
        return self._interactive_mode

    @interactive_mode.setter
    def interactive_mode(self, value):
        if self._interactive_mode != value:
            self._interactive_mode = value
            if value:
                log.debug("working in interative mode")
            else:
                log.debug("working in noninteractive mode")

    @property
    def gui_mode(self):
        """Report if Anaconda should run with the GUI."""
        return self._display_mode == DisplayModes.GUI

    @property
    def tui_mode(self):
        """Report if Anaconda should run with the TUI."""
        return self._display_mode == DisplayModes.TUI

    def log_display_mode(self):
        if not self.display_mode:
            log.error("Display mode is not set!")
            return

        log.info("Display mode is set to '%s %s'.",
                 constants.INTERACTIVE_MODE_NAME[self.interactive_mode],
                 constants.DISPLAY_MODE_NAME[self.display_mode])

    def add_additional_repositories_to_ksdata(self):
        from pyanaconda.kickstart import RepoData

        for add_repo in self.additional_repos:
            name, repo_url = self._get_additional_repo_name(add_repo)
            try:
                source = SourceFactory.parse_repo_cmdline_string(repo_url)
            except PayloadSourceTypeUnrecognized:
                log.error("Type for additional repository %s is not recognized!", add_repo)
                return

            repo = RepoData(name=name, baseurl=repo_url, install=False)

            if source.is_nfs or source.is_http or source.is_https or source.is_ftp \
                    or source.is_file:
                repo.enabled = True
            elif source.is_harddrive:
                repo.enabled = True
                repo.partition = source.partition
                repo.iso_path = source.path
                repo.baseurl = "file://"
            else:
                log.error("Source type %s for additional repository %s is not supported!",
                          source.source_type.value, add_repo)
                continue

            self._check_repo_name_uniqueness(repo)
            self.ksdata.repo.dataList().append(repo)

    def _check_repo_name_uniqueness(self, repo):
        """Log if we are adding repository with already used name

        In automatic kickstart installation this will result in using the first defined repo.
        """
        if repo in self.ksdata.repo.dataList():
            log.warning("Repository name %s is not unique. Only the first repo will be used!",
                        repo.name)

    def _set_default_fstype(self, storage):
        fstype = None
        boot_fstype = None

        # Get the default fstype from a kickstart file.
        auto_part_proxy = STORAGE.get_proxy(AUTO_PARTITIONING)

        if auto_part_proxy.Enabled and auto_part_proxy.FilesystemType:
            fstype = auto_part_proxy.FilesystemType
            boot_fstype = fstype
        # Or from an install class.
        elif self.instClass.defaultFS:
            fstype = self.instClass.defaultFS
            boot_fstype = None

        # Set the default fstype.
        if fstype:
            storage.set_default_fstype(fstype)

        # Set the default boot fstype.
        if boot_fstype:
            storage.set_default_boot_fstype(boot_fstype)

        # Set the default LUKS version.
        luks_version = self.instClass.default_luks_version

        if luks_version:
            storage.set_default_luks_version(luks_version)

    def _load_plugin_s390(self):
        # Make sure s390 plugin is loaded.
        import gi
        gi.require_version("BlockDev", "2.0")
        from gi.repository import BlockDev as blockdev

        # Is the plugin loaded? We are done then.
        if "s390" in blockdev.get_available_plugin_names():
            return

        # Otherwise, load the plugin.
        plugin = blockdev.PluginSpec()
        plugin.name = blockdev.Plugin.S390
        plugin.so_name = None
        blockdev.reinit([plugin], reload=False)

    def dumpState(self):
        from meh import ExceptionInfo
        from meh.dump import ReverseExceptionDump
        from inspect import stack as _stack
        from traceback import format_stack

        # Skip the frames for dumpState and the signal handler.
        stack = _stack()[2:]
        stack.reverse()
        exn = ReverseExceptionDump(ExceptionInfo(None, None, stack),
                                   self.mehConfig)

        # gather up info on the running threads
        threads = "\nThreads\n-------\n"

        # Every call to sys._current_frames() returns a new dict, so it is not
        # modified when threads are created or destroyed. Iterating over it is
        # thread safe.
        for thread_id, frame in sys._current_frames().items():
            threads += "\nThread %s\n" % (thread_id,)
            threads += "".join(format_stack(frame))

        # dump to a unique file
        (fd, filename) = mkstemp(prefix="anaconda-tb-", dir="/tmp")
        dump_text = exn.traceback_and_object_dump(self)
        dump_text += threads
        dump_text_bytes = dump_text.encode("utf-8")
        os.write(fd, dump_text_bytes)
        os.close(fd)

        # append to a given file
        with open("/tmp/anaconda-tb-all.log", "a+") as f:
            f.write("--- traceback: %s ---\n" % filename)
            f.write(dump_text + "\n")

    def initInterface(self, addon_paths=None):
        if self._intf:
            raise RuntimeError("Second attempt to initialize the InstallInterface")

        if self.gui_mode:
            from pyanaconda.ui.gui import GraphicalUserInterface
            # Run the GUI in non-fullscreen mode, so live installs can still
            # use the window manager
            self._intf = GraphicalUserInterface(self.storage, self.payload,
                                                self.instClass, gui_lock=self.gui_initialized,
                                                fullscreen=False, decorated=self.decorated)

            # needs to be refreshed now we know if gui or tui will take place
            addon_paths = addons.collect_addon_paths(constants.ADDON_PATHS,
                                                     ui_subdir="gui")
        elif self.tui_mode:
            # TUI and noninteractive TUI are the same in this regard
            from pyanaconda.ui.tui import TextUserInterface
            self._intf = TextUserInterface(self.storage, self.payload,
                                           self.instClass)

            # needs to be refreshed now we know if gui or tui will take place
            addon_paths = addons.collect_addon_paths(constants.ADDON_PATHS,
                                                     ui_subdir="tui")
        elif not self.display_mode:
            raise RuntimeError("Display mode not set.")
        else:
            # this should generally never happen, as display_mode now won't let
            # and invalid value to be set, but let's leave it here just in case
            # something ultra crazy happens
            raise RuntimeError("Unsupported display mode: %s" % self.display_mode)

        if addon_paths:
            self._intf.update_paths(addon_paths)

    def postConfigureInstallClass(self):
        """Do an install class late configuration.

        This will enable to configure payload.
        """
        self.instClass.configurePayload(self.payload)

    def writeXdriver(self, root=None):
        # this should go away at some point, but until it does, we
        # need to keep it around.
        if self.xdriver is None:
            return
        if root is None:
            root = util.getSysroot()
        if not os.path.isdir("%s/etc/X11" %(root,)):
            os.makedirs("%s/etc/X11" %(root,), mode=0o755)
        f = open("%s/etc/X11/xorg.conf" %(root,), 'w')
        f.write('Section "Device"\n\tIdentifier "Videocard0"\n\tDriver "%s"\nEndSection\n' % self.xdriver)
        f.close()
