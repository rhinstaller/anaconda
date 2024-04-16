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
from pyanaconda.core import util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import ANACONDA_CLEANUP, THREAD_STORAGE, QUIT_MESSAGE
from pyanaconda.modules.common.constants.objects import DEVICE_TREE
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.modules.common.errors.storage import MountFilesystemError
from pyanaconda.modules.common.structures.storage import OSData, DeviceFormatData
from pyanaconda.modules.common.task import sync_run_task
from pyanaconda.threading import threadMgr
from pyanaconda.flags import flags
from pyanaconda.core.i18n import _, N_
from pyanaconda.kickstart import runPostScripts
from pyanaconda.ui.tui import tui_quit_callback
from pyanaconda.ui.tui.spokes import NormalTUISpoke

from pykickstart.constants import KS_REBOOT, KS_SHUTDOWN

from simpleline import App
from simpleline.render.adv_widgets import YesNoDialog, PasswordDialog
from simpleline.render.containers import ListColumnContainer
from simpleline.render.prompt import Prompt
from simpleline.render.screen import InputState
from simpleline.render.screen_handler import ScreenHandler
from simpleline.render.widgets import TextWidget, CheckboxWidget

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
    if conf.target.is_image:
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

        Initialization:
        rescue_data - data of rescue command seen in kickstart
                      <pykickstart.commands.rescue.XX_Rescue>
        reboot      - flag for rebooting after finishing
                      bool
        scritps     - kickstart scripts to be run after mounting root
                      <pyanaconda.kickstart.AnacondaKSScript>

    """
    def __init__(self, rescue_data=None, reboot=False, scripts=None, rescue_nomount=True):
        self._storage_proxy = STORAGE.get_proxy()
        self._device_tree_proxy = STORAGE.get_proxy(DEVICE_TREE)

        self._scripts = scripts
        self.reboot = reboot
        self.automated = False
        self.mount = False
        self.ro = False

        self.autorelabel = False

        self.status = RescueModeStatus.NOT_SET
        self.error = None

        if rescue_data:
            self.automated = True
            self.mount = not (rescue_data.nomount or rescue_nomount)
            self.ro = rescue_data.romount

    def initialize(self):
        threadMgr.wait(THREAD_STORAGE)
        create_etc_symlinks()

    def find_roots(self):
        """List of found roots."""
        task_path = self._device_tree_proxy.FindExistingSystemsWithTask()

        task_proxy = STORAGE.get_proxy(task_path)
        sync_run_task(task_proxy)

        # Collect existing systems.
        roots = OSData.from_structure_list(
            self._device_tree_proxy.GetExistingSystems()
        )

        # Ignore systems without a root device.
        roots = [r for r in roots if r.get_root_device()]

        if not roots:
            self.status = RescueModeStatus.ROOT_NOT_FOUND

        log.debug("These systems were found: %s", str(roots))
        return roots

    # TODO separate running post scripts?
    def mount_root(self, root):
        """Mounts selected root and runs scripts."""
        # mount root fs
        try:
            task_path = self._device_tree_proxy.MountExistingSystemWithTask(
                root.get_root_device(),
                self.ro
            )
            task_proxy = STORAGE.get_proxy(task_path)
            sync_run_task(task_proxy)
            log.info("System has been mounted under: %s", conf.target.system_root)
        except MountFilesystemError as e:
            log.error("Mounting system under %s failed: %s", conf.target.system_root, e)
            self.status = RescueModeStatus.MOUNT_FAILED
            self.error = e
            return False

        # turn on selinux also
        if conf.security.selinux:
            # we have to catch the possible exception, because we
            # support read-only mounting
            try:
                fd = open("%s/.autorelabel" % conf.target.system_root, "w+")
                fd.close()
                self.autorelabel = True
            except IOError as e:
                log.warning("Error turning on selinux: %s", e)

        # set a libpath to use mounted fs
        libdirs = os.environ.get("LD_LIBRARY_PATH", "").split(":")
        mounted = ["/mnt/sysimage%s" % ldir for ldir in libdirs]
        util.setenv("LD_LIBRARY_PATH", ":".join(libdirs + mounted))

        # do we have bash?
        try:
            if os.access("/usr/bin/bash", os.R_OK):
                os.symlink("/usr/bin/bash", "/bin/bash")
        except OSError as e:
            log.error("Error symlinking bash: %s", e)

        # make resolv.conf in chroot
        if not self.ro:
            try:
                makeResolvConf(conf.target.system_root)
            except(OSError, IOError) as e:
                log.error("Error making resolv.conf: %s", e)

        # create /etc/fstab in ramdisk so it's easier to work with RO mounted fs
        makeFStab()

        # run %post if we've mounted everything
        if not self.ro and self._scripts:
            runPostScripts(self._scripts)

        self.status = RescueModeStatus.MOUNTED
        return True

    def get_locked_device_names(self):
        """Get a list of names of locked LUKS devices.

        All LUKS devices are considered locked.
        """
        device_names = []

        for device_name in self._device_tree_proxy.GetDevices():
            format_data = DeviceFormatData.from_structure(
                self._device_tree_proxy.GetFormatData(device_name)
            )

            if not format_data.type == "luks":
                continue

            device_names.append(device_name)

        return device_names

    def unlock_device(self, device_name, passphrase):
        """Unlocks LUKS device."""
        return self._device_tree_proxy.UnlockDevice(device_name, passphrase)

    def run_shell(self):
        """Launch a shell."""
        if os.path.exists("/bin/bash"):
            util.execConsole()
        else:
            # TODO: FIXME -> move to UI (check via module api?)
            print(_("Unable to find /bin/bash to execute!  Not starting shell."))
            time.sleep(5)

    def finish(self, delay=0):
        """Finish rescue mode with optional delay."""
        time.sleep(delay)
        if self.reboot:
            util.execWithRedirect("systemctl", ["--no-wall", "reboot"])


class RescueModeSpoke(NormalTUISpoke):
    """UI offering mounting existing installation roots in rescue mode."""

    # If it acts like a spoke and looks like a spoke, is it a spoke? Not
    # always. This is independent of any hub(s), so pass in some fake data
    def __init__(self, rescue):
        super().__init__(data=None, storage=None, payload=None)
        self.title = N_("Rescue")
        self._container = None
        self._rescue = rescue

    def refresh(self, args=None):
        super().refresh(args)

        msg = _("The rescue environment will now attempt "
                "to find your Linux installation and mount it under "
                "the directory : %s.  You can then make any changes "
                "required to your system.  Choose '1' to proceed with "
                "this step.\nYou can choose to mount your file "
                "systems read-only instead of read-write by choosing "
                "'2'.\nIf for some reason this process does not work "
                "choose '3' to skip directly to a shell.\n\n") % (conf.target.system_root)
        self.window.add_with_separator(TextWidget(msg))

        self._container = ListColumnContainer(1)

        self._container.add(TextWidget(_("Continue")), self._read_write_mount_callback)
        self._container.add(TextWidget(_("Read-only mount")), self._read_only_mount_callback)
        self._container.add(TextWidget(_("Skip to shell")), self._skip_to_shell_callback)
        self._container.add(TextWidget(_("Quit (Reboot)")), self._quit_callback)

        self.window.add_with_separator(self._container)

    def _read_write_mount_callback(self, data):
        self._mount_and_prompt_for_shell()

    def _read_only_mount_callback(self, data):
        self._rescue.ro = True
        self._mount_and_prompt_for_shell()

    def _skip_to_shell_callback(self, data):
        self._show_result_and_prompt_for_shell()

    def _quit_callback(self, data):
        d = YesNoDialog(_(QUIT_MESSAGE))
        ScreenHandler.push_screen_modal(d)
        self.redraw()
        if d.answer:
            self._rescue.reboot = True
            self._rescue.finish()

    def _mount_and_prompt_for_shell(self):
        self._rescue.mount = True
        self._mount_root()
        self._show_result_and_prompt_for_shell()

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
        if self._container.process_user_input(key):
            return InputState.PROCESSED
        else:
            return InputState.DISCARDED

    def _mount_root(self):
        # decrypt all luks devices
        self._unlock_devices()
        roots = self._rescue.find_roots()

        if not roots:
            return

        if len(roots) == 1:
            root = roots[0]
        else:
            # have to prompt user for which root to mount
            root_spoke = RootSelectionSpoke(roots)
            ScreenHandler.push_screen_modal(root_spoke)
            self.redraw()

            root = root_spoke.selection

        self._rescue.mount_root(root)

    def _show_result_and_prompt_for_shell(self):
        new_spoke = RescueStatusAndShellSpoke(self._rescue)
        ScreenHandler.push_screen_modal(new_spoke)
        self.close()

    def _unlock_devices(self):
        """Attempt to unlock all locked LUKS devices."""
        passphrase = None

        for device_name in self._rescue.get_locked_device_names():
            while True:
                if passphrase is None:
                    dialog = PasswordDialog(device_name)
                    ScreenHandler.push_screen_modal(dialog)
                    if not dialog.answer:
                        break

                    passphrase = dialog.answer.strip()

                if self._rescue.unlock_device(device_name, passphrase):
                    break

                passphrase = None

    def apply(self):
        """Move along home."""
        pass


class RescueStatusAndShellSpoke(NormalTUISpoke):
    """UI displaying status of rescue mode mount and prompt for shell."""

    def __init__(self, rescue):
        super().__init__(data=None, storage=None, payload=None)
        self.title = N_("Rescue Shell")
        self._rescue = rescue

    @property
    def indirect(self):
        return True

    def refresh(self, args=None):
        super().refresh(args)

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

                autorelabel_msg = (_("Warning: The rescue shell will trigger SELinux autorelabel "
                                     "on the subsequent boot. Add \"enforcing=0\" on the kernel "
                                     "command line for autorelabel to work properly.\n")
                                   if self._rescue.autorelabel else "")

                text = TextWidget(_("Your system has been mounted under %(mountpoint)s.\n\n"
                                    "If you would like to make the root of your system the "
                                    "root of the active system, run the command:\n\n"
                                    "\tchroot %(mountpoint)s\n\n")
                                  % {"mountpoint": conf.target.system_root} + autorelabel_msg
                                  + finish_msg)
            elif status == RescueModeStatus.MOUNT_FAILED:
                if self._rescue.reboot:
                    finish_msg = exit_reboot_msg
                else:
                    finish_msg = umount_msg

                msg = _(
                    "An error occurred trying to mount some or all of your system: "
                    "{message}\n\nSome of it may be mounted under {path}.").format(
                    message=str(self._rescue.error),
                    path=conf.target.system_root
                )

                text = TextWidget(msg + " " + finish_msg)
            elif status == RescueModeStatus.ROOT_NOT_FOUND:
                if self._rescue.reboot:
                    finish_msg = exit_reboot_msg
                else:
                    finish_msg = ""
                text = TextWidget(_("You don't have any Linux partitions.\n") + finish_msg)
        else:
            if self._rescue.reboot:
                finish_msg = exit_reboot_msg
            else:
                finish_msg = ""
            text = TextWidget(_("Not mounting the system.\n") + finish_msg)

        self.window.add(text)

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
        super().__init__(data=None, storage=None, payload=None)
        self.title = N_("Root Selection")
        self._roots = roots
        self._selection = roots[0]
        self._container = None

    @property
    def selection(self):
        """The selected root fs to mount."""
        return self._selection

    @property
    def indirect(self):
        return True

    def refresh(self, args=None):
        super().refresh(args)
        self._container = ListColumnContainer(1)

        for root in self._roots:
            box = CheckboxWidget(
                title="{} on {}".format(root.os_name, root.get_root_device()),
                completed=(self._selection == root)
            )

            self._container.add(box, self._select_root, root)

        message = _("The following installations were discovered on your system.")
        self.window.add_with_separator(TextWidget(message))
        self.window.add_with_separator(self._container)

    def _select_root(self, root):
        self._selection = root

    def prompt(self, args=None):
        """ Override the default TUI prompt."""
        prompt = Prompt()
        prompt.add_continue_option()
        return prompt

    def input(self, args, key):
        """Override any input so we can launch rescue mode."""
        if self._container.process_user_input(key):
            return InputState.PROCESSED_AND_REDRAW
        elif key == Prompt.CONTINUE:
            return InputState.PROCESSED_AND_CLOSE
        else:
            return key

    def apply(self):
        """Define the abstract method."""
        pass


def start_rescue_mode_ui(anaconda):
    """Start the rescue mode UI."""

    ksdata_rescue = None
    if anaconda.ksdata.rescue.seen:
        ksdata_rescue = anaconda.ksdata.rescue
    scripts = anaconda.ksdata.scripts
    rescue_nomount = anaconda.opts.rescue_nomount
    reboot = True
    if conf.target.is_image:
        reboot = False
    if flags.automatedInstall and anaconda.ksdata.reboot.action not in [KS_REBOOT, KS_SHUTDOWN]:
        reboot = False

    rescue = Rescue(ksdata_rescue, reboot, scripts, rescue_nomount)
    rescue.initialize()

    # We still want to choose from multiple roots, or unlock encrypted devices
    # if needed, so we run UI even for kickstarts (automated install).
    App.initialize()
    loop = App.get_event_loop()
    loop.set_quit_callback(tui_quit_callback)
    spoke = RescueModeSpoke(rescue)
    ScreenHandler.schedule_screen(spoke)
    App.run()
