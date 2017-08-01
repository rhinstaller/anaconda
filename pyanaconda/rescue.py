#
# rescue.py - anaconda rescue mode setup
#
# Copyright (C) 2015 Red Hat, Inc.  All rights reserved.
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
from blivet.errors import StorageError
from blivet.devices import LUKSDevice
from blivet.osinstall import mount_existing_system, find_existing_installations

from pyanaconda import iutil
from pyanaconda.constants import ANACONDA_CLEANUP, THREAD_STORAGE
from pyanaconda.threading import threadMgr
from pyanaconda.flags import flags
from pyanaconda.i18n import _, N_, C_
from pyanaconda.kickstart import runPostScripts
from pyanaconda.ui.tui.spokes import NormalTUISpoke
from pyanaconda.storage_utils import try_populate_devicetree

from pykickstart.constants import KS_REBOOT, KS_SHUTDOWN

from simpleline import App
from simpleline.render.adv_widgets import YesNoDialog, PasswordDialog
from simpleline.render.prompt import Prompt
from simpleline.render.screen import InputState
from simpleline.render.screen_handler import ScreenHandler
from simpleline.render.widgets import TextWidget, ColumnWidget, CheckboxWidget

import os
import shutil
import time
from enum import Enum

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["RescueModeSpoke", "RootSelectionSpoke", "RescueStatusAndShellSpoke"]


def makeFStab(instPath=""):
    """Make the fs tab."""
    if os.access("/proc/mounts", os.R_OK):
        f = open("/proc/mounts", "r")
        buf = f.read()
        f.close()
    else:
        buf = ""

    try:
        f = open(instPath + "/etc/fstab", "a")
        if buf:
            f.write(buf)
        f.close()
    except IOError as e:
        log.info("failed to write /etc/fstab: %s", e)


def makeResolvConf(instPath):
    """Make the resolv.conf file in the chroot."""
    if flags.imageInstall:
        return

    if not os.access("/etc/resolv.conf", os.R_OK):
        return

    if os.access("%s/etc/resolv.conf" %(instPath,), os.R_OK):
        f = open("%s/etc/resolv.conf" %(instPath,), "r")
        buf = f.read()
        f.close()
    else:
        buf = ""

    # already have a nameserver line, don't worry about it
    if buf.find("nameserver") != -1:
        return

    f = open("/etc/resolv.conf", "r")
    buf = f.read()
    f.close()

    # no nameserver, we can't do much about it
    if buf.find("nameserver") == -1:
        return

    shutil.copyfile("%s/etc/resolv.conf" %(instPath,),
                    "%s/etc/resolv.conf.bak" %(instPath,))
    f = open("%s/etc/resolv.conf" %(instPath,), "w+")
    f.write(buf)
    f.close()


def create_etc_symlinks():
    """I don't know why I live. Maybe I should be killed."""
    for f in ["services", "protocols", "group", "man.config",
              "nsswitch.conf", "selinux", "mke2fs.conf"]:
        try:
            os.symlink('/mnt/runtime/etc/' + f, '/etc/' + f)
        except OSError:
            log.debug("Failed to create symlink for /mnt/runtime/etc/%s", f)


class RescueModeStatus(Enum):
    """Status of rescue mode environment."""
    NOT_SET = "not set"
    MOUNTED = "mounted"
    MOUNT_FAILED = "mount failed"
    ROOT_NOT_FOUND = "root not found"


class EncryptedDeviceState(object):
    """A container for encrypted device and its state."""
    def __init__(self, device, passphrase="", locked=True):
        self._device = device
        self._passphrase = passphrase
        self._locked = locked

    def set_unlocked(self, passphrase):
        """Mark the device as unlocked."""
        self._passphrase = passphrase
        self._locked = False

    @property
    def locked(self):
        """Is the device locked?"""
        return self._locked

    @property
    def device(self):
        """The device object (blivet)."""
        return self._device


class Rescue(object):
    """Rescue mode module.

        Provides interface to:
        - find and unlock encrypted devices
        - find existing systems
        - mount selected existing system and run kickstart scripts
        - run interactive shell
        - finish the environment (reboot)

        Dependencies:
        - storage module
        - storage initialization thread
        - global flags: imageInstall

        Initialization:
        storage     - storage object
                      <blivet.blivet.Blivet>
        rescue_data - data of rescue command seen in kickstart
                      <pykickstart.commands.rescue.XX_Rescue>
        reboot      - flag for rebooting after finishing
                      bool
        scritps     - kickstart scripts to be run after mounting root
                      <pyanaconda.kickstart.AnacondaKSScript>

    """
    def __init__(self, storage, rescue_data=None, reboot=False, scripts=None):

        self._storage = storage
        self._scripts = scripts

        self.reboot = reboot
        self.automated = False
        self.mount = False
        self.ro = False

        self._roots = None
        self._selected_root = 1
        self._luks_devices_states = None

        self.status = RescueModeStatus.NOT_SET

        if rescue_data:
            self.automated = True
            self.mount = not rescue_data.nomount
            self.ro = rescue_data.romount

    def initialize(self):
        threadMgr.wait(THREAD_STORAGE)
        create_etc_symlinks()

    @property
    def roots(self):
        """List of found roots."""
        if self._roots is None:
            self._roots = find_existing_installations(self._storage.devicetree)
            if not self._roots:
                self.status = RescueModeStatus.ROOT_NOT_FOUND
        return self._roots

    def get_found_root_infos(self):
        """List of descriptions of found roots."""
        roots = [(root.name, root.device.path) for root in self.roots]
        return roots

    @property
    def root(self):
        """Selected root."""
        if self._selected_root <= len(self.roots):
            return self.roots[self._selected_root-1]
        else:
            return None

    def select_root(self, index):
        """Select root from a list of found roots."""
        self._selected_root = index

    # TODO separate running post scripts?
    def mount_root(self):
        """Mounts selected root and runs scripts."""
        # mount root fs
        try:
            mount_existing_system(self._storage.fsset, self.root.device, read_only=self.ro)
            log.info("System has been mounted under: %s", iutil.getSysroot())
        except StorageError as e:
            log.error("Mounting system under %s failed: %s", iutil.getSysroot(), e)
            self.status = RescueModeStatus.MOUNT_FAILED
            return False

        # turn on swap
        if not flags.imageInstall or not self.ro:
            try:
                self._storage.turn_on_swap()
            except StorageError:
                log.error("Error enabling swap.")

        # turn on selinux also
        if flags.selinux:
            # we have to catch the possible exception, because we
            # support read-only mounting
            try:
                fd = open("%s/.autorelabel" % iutil.getSysroot(), "w+")
                fd.close()
            except IOError as e:
                log.warning("Error turning on selinux: %s", e)

        # set a libpath to use mounted fs
        libdirs = os.environ.get("LD_LIBRARY_PATH", "").split(":")
        mounted = ["/mnt/sysimage%s" % ldir for ldir in libdirs]
        iutil.setenv("LD_LIBRARY_PATH", ":".join(libdirs + mounted))

        # do we have bash?
        try:
            if os.access("/usr/bin/bash", os.R_OK):
                os.symlink("/usr/bin/bash", "/bin/bash")
        except OSError as e:
            log.error("Error symlinking bash: %s", e)

        # make resolv.conf in chroot
        if not self.ro:
            self._storage.make_mtab()
            try:
                makeResolvConf(iutil.getSysroot())
            except(OSError, IOError) as e:
                log.error("Error making resolv.conf: %s", e)

        # create /etc/fstab in ramdisk so it's easier to work with RO mounted fs
        makeFStab()

        # run %post if we've mounted everything
        if not self.ro and self._scripts:
            runPostScripts(self._scripts)

        self.status = RescueModeStatus.MOUNTED
        return True

    @property
    def luks_devices_states(self):
        """List of objects representing LUKS devices and their state."""
        if self._luks_devices_states is None:
            ldevs = [dev for dev in self._storage.devices if dev.format.type == "luks"]
            self._luks_devices_states = [EncryptedDeviceState(dev) for dev in ldevs]
        return self._luks_devices_states

    def get_locked_device_names(self):
        """List of names of unlocked LUKS devices."""
        device_names = [device_state.device.name for device_state
                        in self.luks_devices_states if device_state.locked]
        return device_names

    def _find_device_state(self, device_name):
        for device_state in self.luks_devices_states:
            if device_state.device.name == device_name:
                return device_state
        return None

    def unlock_device(self, device_name, passphrase):
        """Unlocks LUKS device."""
        device_state = self._find_device_state(device_name)
        if device_state is None:
            # TODO: raise an exception?
            log.error("Can't find device to unlock %s", device_name)
            return False

        device = device_state.device
        device.format.passphrase = passphrase
        try:
            device.setup()
            device.format.setup()
            luks_device = LUKSDevice(device.format.map_name,
                                     parents=[device],
                                     exists=True)
            self._storage.devicetree._add_device(luks_device)

            # Wait for the device.
            # Otherwise, we could get a message about no Linux partitions.
            time.sleep(2)

            try_populate_devicetree(self._storage.devicetree)
        except StorageError as serr:
            log.error("Failed to unlock %s: %s", device.name, serr)
            device.teardown(recursive=True)
            device.format.passphrase = None
            return False
        else:
            device_state.set_unlocked(passphrase)
            return True

    def run_shell(self):
        """Launch a shell."""
        if os.path.exists("/bin/bash"):
            iutil.execConsole()
        else:
            # TODO: FIXME -> move to UI (check via module api?)
            print(_("Unable to find /bin/bash to execute!  Not starting shell."))
            time.sleep(5)

    def finish(self, delay=0):
        """Finish rescue mode with optional delay."""
        time.sleep(delay)
        if self.reboot:
            iutil.execWithRedirect("systemctl", ["--no-wall", "reboot"])

    def run_without_ui(self):
        if self.mount:
            if self.get_locked_device_names():
                log.warning("Locked LUKS devices found.")
            if self.root:
                self.mount_root()
            else:
                log.warning("No Linux partitions found.")
        self.run_shell()
        self.finish()


class RescueModeSpoke(NormalTUISpoke):
    """UI offering mounting existing installation roots in rescue mode."""

    # If it acts like a spoke and looks like a spoke, is it a spoke? Not
    # always. This is independent of any hub(s), so pass in some fake data
    def __init__(self, rescue):
        NormalTUISpoke.__init__(self, data=None, storage=None, payload=None, instclass=None)
        self.title = N_("Rescue")
        self._choices = (_("Continue"), _("Read-only mount"), _("Skip to shell"), ("Quit (Reboot)"))
        self._rescue = rescue

    def refresh(self, args=None):
        NormalTUISpoke.refresh(self, args)

        msg = _("The rescue environment will now attempt "
                "to find your Linux installation and mount it under "
                "the directory : %s.  You can then make any changes "
                "required to your system.  Choose '1' to proceed with "
                "this step.\nYou can choose to mount your file "
                "systems read-only instead of read-write by choosing "
                "'2'.\nIf for some reason this process does not work "
                "choose '3' to skip directly to a shell.\n\n") % (iutil.getSysroot())
        self.window.add_with_separator(TextWidget(msg))

        for idx, choice in enumerate(self._choices):
            number = TextWidget("%2d)" % (idx + 1))
            c = ColumnWidget([(3, [number]), (None, [TextWidget(choice)])], 1)
            self.window.add_with_separator(c)

    def prompt(self, args=None):
        """ Override the default TUI prompt."""
        if self._rescue.automated:
            if self._rescue.mount:
                self._mount_root()
            self._show_result_and_prompt_for_shell()
            return None
        return Prompt()

    def input(self, args, key):
        """Override any input so we can launch rescue mode."""
        keyid = None
        try:
            keyid = int(key) - 1
        except ValueError:
            pass

        if keyid == 3:
            # quit/reboot
            d = YesNoDialog(_(u"Do you really want to quit?"))
            ScreenHandler.push_screen_modal(d)
            self.redraw()
            if d.answer:
                self._rescue.reboot = True
                self._rescue.finish()
        elif keyid == 2:
            # skip to/run shell
            self._show_result_and_prompt_for_shell()
        elif keyid == 1 or keyid == 0:
            # user chose 0 (continue/rw-mount) or 1 (ro-mount)
            self._rescue.mount = True
            if keyid == 1:
                self._rescue.ro = True
            self._mount_root()
            self._show_result_and_prompt_for_shell()
        else:
            # user entered some invalid number choice
            return key

        return InputState.PROCESSED

    def _mount_root(self):
        # decrypt all luks devices
        self._unlock_devices()
        found_roots = self._rescue.get_found_root_infos()
        if len(found_roots) > 1:
            # have to prompt user for which root to mount
            root_spoke = RootSelectionSpoke(found_roots)
            ScreenHandler.push_screen_modal(root_spoke)
            self.redraw()
            self._rescue.select_root(root_spoke.selection)
        self._rescue.mount_root()

    def _show_result_and_prompt_for_shell(self):
        new_spoke = RescueStatusAndShellSpoke(self._rescue)
        ScreenHandler.push_screen_modal(new_spoke)
        self.close()

    def _unlock_devices(self):
        """Attempt to unlock all locked LUKS devices.

        Returns true if all devices were unlocked.
        """
        try_passphrase = None
        passphrase = None
        for device_name in self._rescue.get_locked_device_names():
            skip = False
            unlocked = False
            while not (skip or unlocked):
                if try_passphrase is None:
                    p = PasswordDialog(device_name)
                    ScreenHandler.push_screen_modal(p)
                    if p.answer:
                        passphrase = p.answer.strip()
                else:
                    passphrase = try_passphrase

                if passphrase is None:
                    # cancelled
                    skip = True
                else:
                    unlocked = self._rescue.unlock_device(device_name, passphrase)
                    try_passphrase = passphrase if unlocked else None

        return not self._rescue.get_locked_device_names()

    def apply(self):
        """Move along home."""
        pass


class RescueStatusAndShellSpoke(NormalTUISpoke):
    """UI displaying status of rescue mode mount and prompt for shell."""

    def __init__(self, rescue):
        NormalTUISpoke.__init__(self, data=None, storage=None, payload=None, instclass=None)
        self.title = N_("Rescue Shell")
        self._rescue = rescue

    @property
    def indirect(self):
        return True

    def refresh(self, args=None):
        NormalTUISpoke.refresh(self, args)

        umount_msg = _("Run %s to unmount the system when you are finished.") % ANACONDA_CLEANUP
        exit_reboot_msg = _("When finished, please exit from the shell and your "
                            "system will reboot.\n")
        text = None

        if self._rescue.mount:
            status = self._rescue.status
            if status == RescueModeStatus.MOUNTED:
                if self._rescue.reboot:
                    finish_msg = exit_reboot_msg
                else:
                    finish_msg = umount_msg
                text = TextWidget(_("Your system has been mounted under %(mountpoint)s.\n\n"
                                    "If you would like to make the root of your system the "
                                    "root of the active system, run the command:\n\n"
                                    "\tchroot %(mountpoint)s\n")
                                    % {"mountpoint": iutil.getSysroot()} + finish_msg)
            elif status == RescueModeStatus.MOUNT_FAILED:
                if self._rescue.reboot:
                    finish_msg = exit_reboot_msg
                else:
                    finish_msg = umount_msg
                text = TextWidget(_("An error occurred trying to mount some or all of "
                                    "your system.  Some of it may be mounted under %s\n\n") % iutil.getSysroot() + finish_msg)
            elif status == RescueModeStatus.ROOT_NOT_FOUND:
                if self._rescue.reboot:
                    finish_msg = _("Rebooting.")
                else:
                    finish_msg = ""
                text = TextWidget(_("You don't have any Linux partitions. %s\n") % finish_msg)
        else:
            if self._rescue.reboot:
                finish_msg = exit_reboot_msg
            else:
                finish_msg = ""
            text = TextWidget(_("Not mounting the system.\n") + finish_msg)

        self.window.add(text)
        return InputState.PROCESSED

    def prompt(self, args=None):
        """ Override the default TUI prompt."""
        if self._rescue.automated:
            if self._rescue.reboot and self._rescue.status == RescueModeStatus.ROOT_NOT_FOUND:
                delay = 5
            else:
                delay = 0
                self._rescue.run_shell()
            self._rescue.finish(delay=delay)
            return None
        return Prompt(_("Please press %s to get a shell") % Prompt.ENTER)

    def input(self, args, key):
        """Move along home."""
        self._rescue.run_shell()
        self._rescue.finish()
        return InputState.PROCESSED

    def apply(self):
        pass


class RootSelectionSpoke(NormalTUISpoke):
    """UI for selection of installed system root to be mounted."""

    def __init__(self, roots):
        NormalTUISpoke.__init__(self, data=None, storage=None, payload=None, instclass=None)
        self.title = N_("Root Selection")
        self._roots = roots
        self._selection = 0

    @property
    def indirect(self):
        return True

    def refresh(self, args=None):
        NormalTUISpoke.refresh(self, args)

        message = _("The following installations were discovered on your system.\n")
        self.window.add_with_separator(TextWidget(message))

        for i, root_desc in enumerate(self._roots):
            root_name, root_device_path = root_desc
            box = CheckboxWidget(title="%i) %s on %s" % (i + 1, _(root_name), root_device_path),
                                 completed=(self._selection == i))
            self.window.add_with_separator(box)

    def prompt(self, args=None):
        """ Override the default TUI prompt."""
        return Prompt(
                 _("Please make your selection from the above list.\n"
                   "Press '%(continue)s' to continue after you have made your selection") % {
                     # TRANSLATORS:'c' to continue
                     'continue': C_('TUI|Root Selection', 'c'),
                   })

    def input(self, args, key):
        """Move along home."""
        try:
            keyid = int(key) - 1
        except ValueError:
            # TRANSLATORS: 'c' to continue
            if key.lower() == C_('TUI|Spoke Navigation', 'c'):
                self.apply()
                self.close()
                return InputState.PROCESSED
            else:
                return key

        if 0 <= keyid < len(self._roots):
            self._selection = keyid
        self.redraw()
        return InputState.PROCESSED

    @property
    def selection(self):
        """The selected root fs to mount."""
        return self._selection + 1

    def apply(self):
        """Passing the result via selection property."""
        pass


def start_rescue_mode_ui(anaconda):
    """Start the rescue mode UI."""

    ksdata_rescue = None
    if anaconda.ksdata.rescue.seen:
        ksdata_rescue = anaconda.ksdata.rescue
    scripts = anaconda.ksdata.scripts
    storage = anaconda.storage
    reboot = True
    if flags.imageInstall:
        reboot = False
    if flags.automatedInstall and anaconda.ksdata.reboot.action not in [KS_REBOOT, KS_SHUTDOWN]:
        reboot = False

    rescue = Rescue(storage, ksdata_rescue, reboot, scripts)
    rescue.initialize()

    # We still want to choose from multiple roots, or unlock encrypted devices
    # if needed, so we run UI even for kickstarts (automated install).
    App.initialize()
    spoke = RescueModeSpoke(rescue)
    ScreenHandler.schedule_screen(spoke)
    App.run()
