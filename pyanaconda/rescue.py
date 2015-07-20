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
# Author(s): Samantha N. Bueno <sbueno@redhat.com>
#
from blivet.errors import StorageError
from blivet.devices import LUKSDevice
from blivet.osinstall import mountExistingSystem, findExistingInstallations

from pyanaconda import iutil
from pyanaconda.constants import ANACONDA_CLEANUP
from pyanaconda.constants_text import INPUT_PROCESSED
from pyanaconda.flags import flags
from pyanaconda.i18n import _, N_
from pyanaconda.kickstart import runPostScripts
from pyanaconda.ui.tui.simpleline import TextWidget, ColumnWidget, CheckboxWidget
from pyanaconda.ui.tui.spokes import NormalTUISpoke
from pyanaconda.ui.tui.tuiobject import YesNoDialog, PasswordDialog

from pykickstart.constants import KS_REBOOT, KS_SHUTDOWN

from pyanaconda.iutil import open   # pylint: disable=redefined-builtin

import os
import shutil
import time

import logging
log = logging.getLogger("anaconda")

__all__ = ["RescueMode", "RootSpoke", "RescueMountSpoke"]

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

def run_shell():
    """Launch a shell."""
    if flags.imageInstall:
        print(_("Run %s to unmount the system when you are finished.")
                % ANACONDA_CLEANUP)
    else:
        print(_("When finished, please exit from the shell and your "
                "system will reboot."))

    proc = None
    if proc is None or proc.returncode != 0:
        if os.path.exists("/bin/bash"):
            iutil.execConsole()
        else:
            print(_("Unable to find /bin/bash to execute!  Not starting shell."))
            time.sleep(5)

    if not flags.imageInstall:
        iutil.execWithRedirect("systemctl", ["--no-wall", "reboot"])
    else:
        return None

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

class RescueMode(NormalTUISpoke):
    title = N_("Rescue")

    # If it acts like a spoke and looks like a spoke, is it a spoke? Not
    # always. This is independent of any hub(s), so pass in some fake data
    def __init__(self, app, data, storage=None, payload=None, instclass=None):
        NormalTUISpoke.__init__(self, app, data, storage, payload, instclass)
        if flags.automatedInstall:
            self._ro = data.rescue.romount
        else:
            self._ro = False

        self._root = None
        self._choices = (_("Continue"), _("Read-only mount"), _("Skip to shell"), ("Quit (Reboot)"))

    def initialize(self):
        NormalTUISpoke.initialize(self)

        for f in ["services", "protocols", "group", "man.config",
                  "nsswitch.conf", "selinux", "mke2fs.conf"]:
            try:
                os.symlink('/mnt/runtime/etc/' + f, '/etc/' + f)
            except OSError:
                pass

    def prompt(self, args=None):
        """ Override the default TUI prompt."""
        return _("Please make a selection from the above:  ")

    def refresh(self, args=None):
        NormalTUISpoke.refresh(self, args)

        self._window += [TextWidget(_("The rescue environment will now attempt "
                         "to find your Linux installation and mount it under "
                         "the directory : %s.  You can then make any changes "
                         "required to your system.  Choose '1' to proceed with "
                         "this step.\nYou can choose to mount your file "
                         "systems read-only instead of read-write by choosing "
                         "'2'.\nIf for some reason this process does not work "
                         "choose '3' to skip directly to a shell.\n\n") % (iutil.getSysroot())), ""]

        for idx, choice in enumerate(self._choices):
            number = TextWidget("%2d)" % (idx + 1))
            c = ColumnWidget([(3, [number]), (None, [TextWidget(choice)])], 1)
            self._window += [c, ""]

        return True

    def input(self, args, key):
        """Override any input so we can launch rescue mode."""
        try:
            keyid = int(key) - 1
        except ValueError:
            pass

        if keyid == 3:
            # quit/reboot
            d = YesNoDialog(self.app, _(self.app.quit_message))
            self.app.switch_screen_modal(d)
            if d.answer:
                iutil.execWithRedirect("systemctl", ["--no-wall", "reboot"])
        elif keyid == 2:
            # skip to/run shell
            run_shell()
        elif (keyid == 1 or keyid == 0):
            # user chose 0 (continue/rw-mount) or 1 (ro-mount)
            # decrypt any luks devices
            self._unlock_devices()

            # this sleep may look pointless, but it seems necessary, in
            # order for some task to complete; otherwise no existing
            # installations are discovered. IOW, this is a hack.
            time.sleep(2)
            # attempt to find previous installations
            roots = findExistingInstallations(self.storage.devicetree)
            if len(roots) == 1:
                self._root = roots[0]
            elif len(roots) > 1:
                # have to prompt user for which root to mount
                rootspoke = RootSpoke(self.app, self.data, self.storage,
                            self.payload, self.instclass, roots)
                self.app.switch_screen_modal(rootspoke)
                self._root = rootspoke.root

            # if only one root detected, or user has chosen which root
            # to mount, go ahead and do that
            newspoke = RescueMountSpoke(self.app, self.data,
                        self.storage, self.payload, self.instclass, keyid, self._root)
            self.app.switch_screen_modal(newspoke)
            self.close()
        else:
            # user entered some invalid number choice
            return key


        return INPUT_PROCESSED

    def apply(self):
        """Move along home."""
        pass

    def _unlock_devices(self):
        """
            Loop through devices and attempt to unlock any which are detected as
            LUKS devices.
        """
        try_passphrase = None
        for device in self.storage.devices:
            if device.format.type != "luks":
                continue

            skip = False
            unlocked = False
            while not (skip or unlocked):
                if try_passphrase is None:
                    p = PasswordDialog(self.app, device.name)
                    self.app.switch_screen_modal(p)
                    if p.answer:
                        passphrase = p.answer.strip()
                else:
                    passphrase = try_passphrase

                if passphrase is None:
                    # canceled
                    skip = True
                else:
                    device.format.passphrase = passphrase
                    try:
                        device.setup()
                        device.format.setup()
                        luks_dev = LUKSDevice(device.format.mapName,
                                              parents=[device],
                                              exists=True)
                        self.storage.devicetree._addDevice(luks_dev)
                        self.storage.devicetree.populate()
                        unlocked = True
                        # try to use the same passhprase for other devices
                        try_passphrase = passphrase
                    except StorageError as serr:
                        log.error("Failed to unlock %s: %s", device.name, serr)
                        device.teardown(recursive=True)
                        device.format.passphrase = None
                        try_passphrase = None
        return True

class RootSpoke(NormalTUISpoke):
    title = N_("Root Selection")

    def __init__(self, app, data, storage, payload, instclass, roots):
        NormalTUISpoke.__init__(self, app, data, storage, payload, instclass)

        self._root = None
        self._roots = roots
        # default to selecting the first root in the list
        self._selection = 0

    @property
    def indirect(self):
        return True

    def refresh(self, args=None):
        NormalTUISpoke.refresh(self, args)

        message = _("The following installations were discovered on your system.\n")
        self._window += [TextWidget(message), ""]

        for i, root in enumerate(self._roots):
            box = CheckboxWidget(title="%i) %s on %s" % (i + 1, _(root.name), root.device.path),
                                 completed=(self._selection == i))
            self._window += [box, ""]

        return True

    def prompt(self, args=None):
        """ Override the default TUI prompt."""
        return _("Please make your selection from the above list.\nPress 'c' "
                 "to continue after you have made your selection.  ")

    def input(self, args, key):
        """Move along home."""
        try:
            keyid = int(key) - 1
        except ValueError:
            if key.lower() == "c":
                self.apply()
                self.close()
                return INPUT_PROCESSED
            else:
                return key

        if 0 <= keyid < len(self._roots):
            self._selection = keyid
        return INPUT_PROCESSED

    def apply(self):
        """Apply our selection."""
        self._root = self._roots[self._selection]

    @property
    def root(self):
        """The selected root fs to mount."""
        return self._root

class RescueMountSpoke(NormalTUISpoke):
    # 1 = continue/rw-mount, 2 = ro-mount
    title = N_("Rescue Mount")

    def __init__(self, app, data, storage, payload, instclass, selection, root):
        NormalTUISpoke.__init__(self, app, data, storage, payload, instclass)

        self.readOnly = selection
        # root to mount
        self._root = root

    def refresh(self, args=None):
        NormalTUISpoke.refresh(self, args)

        if self._root:
            try:
                mountExistingSystem(self.storage.fsset, self._root.device,
                                    readOnly=self.readOnly)
                if flags.automatedInstall:
                    log.info("System has been mounted under: %s", iutil.getSysroot())
                else:
                    text = TextWidget(_("Your system has been mounted under %(mountpoint)s.\n\nIf "
                                        "you would like to make your system the root "
                                        "environment, run the command:\n\n\tchroot %(mountpoint)s\n")
                                        % {"mountpoint": iutil.getSysroot()} )
                    self._window.append(text)
                rootmounted = True

                # now turn on swap
                if not flags.imageInstall or not self.readOnly:
                    try:
                        self.storage.turnOnSwap()
                    except StorageError:
                        log.error("Error enabling swap.")

                # turn on selinux also
                if flags.selinux:
                    # we have to catch the possible exception, because we
                    # support read-only mounting
                    try:
                        fd = open("%s/.autorelabel" % iutil.getSysroot(), "w+")
                        fd.close()
                    except IOError:
                        log.warning("Cannot touch %s/.autorelabel", iutil.getSysroot())

                # set a libpath to use mounted fs
                libdirs = os.environ.get("LD_LIBRARY_PATH", "").split(":")
                mounted = list(map(lambda dir: "/mnt/sysimage%s" % dir, libdirs))
                iutil.setenv("LD_LIBRARY_PATH", ":".join(libdirs + mounted))

                # do we have bash?
                try:
                    if os.access("/usr/bin/bash", os.R_OK):
                        os.symlink("/usr/bin/bash", "/bin/bash")
                except OSError:
                    pass
            except (ValueError, LookupError, SyntaxError, NameError):
                pass
            except Exception as e: # pylint: disable=broad-except
                if flags.automatedInstall:
                    msg = _("Run %s to unmount the system when you are finished.\n") % ANACONDA_CLEANUP

                text = TextWidget(_("An error occurred trying to mount some or all of "
                                    "your system.  Some of it may be mounted under %s\n\n") + iutil.getSysroot() + msg)
                self._window.append(text)
                return True
        else:
            if flags.automatedInstall and self.data.reboot.action in [KS_REBOOT, KS_SHUTDOWN]:
                log.info("No Linux partitions found.")
                text = TextWidget(_("You don't have any Linux partitions.  Rebooting.\n"))
                self._window.append(text)
                # should probably wait a few seconds to show the message
                time.sleep(5)
                iutil.execWithRedirect("systemctl", ["--no-wall", "reboot"])
            else:
                if not flags.imageInstall:
                    msg = _("The system will reboot automatically when you exit"
                            " from the shell.\n")
                else:
                    msg = ""
            text = TextWidget(_("You don't have any Linux partitions. %s\n") % msg)
            self._window.append(text)
            return True

        if rootmounted and not self.readOnly:
            self.storage.makeMtab()
            try:
                makeResolvConf(iutil.getSysroot())
            except(OSError, IOError) as e:
                log.error("Error making resolv.conf: %s", e)
            text = TextWidget(_("Your system is mounted under the %s directory.") % iutil.getSysroot())
            self._window.append(text)

        # create /etc/fstab in ramdisk so it's easier to work with RO mounted fs
        makeFStab()

        # run %post if we've mounted everything
        if rootmounted and not self.readOnly and flags.automatedInstall:
            runPostScripts(self.data.scripts)

        return True

    def apply(self):
        if flags.automatedInstall and self.data.reboot.action in [KS_REBOOT, KS_SHUTDOWN]:
            iutil.execWithRedirect("systemctl", ["--no-wall", "reboot"])

        if not flags.automatedInstall or not self.data.reboot.action in [KS_REBOOT, KS_SHUTDOWN]:
            run_shell()

    def prompt(self, args=None):
        """ Override the default TUI prompt."""
        return _("Please press <return> to get a shell. ")

    def input(self, args, key):
        """Move along home."""
        run_shell()

        if not flags.imageInstall:
            iutil.execWithRedirect("systemctl", ["--no-wall", "reboot"])

        return INPUT_PROCESSED

    @property
    def indirect(self):
        return True

