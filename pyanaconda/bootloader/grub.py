#
# Copyright (C) 2019 Red Hat, Inc.
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
import crypt
import os
import re

from blivet.devicelibs import raid

from pyanaconda.bootloader.base import BootLoader, BootLoaderError, Arguments
from pyanaconda.bootloader.image import LinuxBootLoaderImage, TbootLinuxBootLoaderImage
from pyanaconda.core import util
from pyanaconda.core.i18n import _

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["GRUB"]


class SerialConsoleOptions(object):
    """The serial console options."""

    def __init__(self):
        self.speed = None
        self.parity = None
        self.word = None
        self.stop = None
        self.flow = None


def _parse_serial_opt(arg):
    """Parse and split serial console options.

    .. NOTE::

       Documentation/kernel-parameters.txt says:

          ttyS<n>[,options]

             Use the specified serial port.  The options are of
             the form "bbbbpnf", where "bbbb" is the baud rate,
             "p" is parity ("n", "o", or "e"), "n" is number of
             bits, and "f" is flow control ("r" for RTS or
             omit it).  Default is "9600n8".

       but note that everything after the baud rate is optional, so these are
       all valid: 9600, 19200n, 38400n8, 9600e7r.
       Also note that the kernel assumes 1 stop bit; this can't be changed.
    """
    opts = SerialConsoleOptions()
    m = re.match(r'\d+', arg)
    if m is None:
        return opts
    opts.speed = m.group()
    idx = len(opts.speed)
    try:
        opts.parity = arg[idx + 0]
        opts.word = arg[idx + 1]
        opts.flow = arg[idx + 2]
    except IndexError:
        pass
    return opts


class GRUB(BootLoader):
    name = "GRUB"
    _config_dir = "grub"
    _config_file = "grub.conf"
    _device_map_file = "device.map"
    can_dual_boot = True
    can_update = True

    stage2_is_valid_stage1 = True
    stage2_bootable = True
    stage2_must_be_primary = False

    # list of strings representing options for boot device types
    stage2_device_types = ["partition", "mdarray"]
    stage2_raid_levels = [raid.RAID1]
    stage2_raid_member_types = ["partition"]
    stage2_raid_metadata = ["0", "0.90", "1.0"]

    packages = ["grub"]

    _serial_consoles = ["ttyS"]

    def __init__(self):
        super().__init__()
        self.encrypted_password = ""

    #
    # grub-related conveniences
    #

    def grub_device_name(self, device):
        """ Return a grub-friendly representation of device. """
        disk = getattr(device, "disk", device)
        name = "(hd%d" % self.disks.index(disk)
        if hasattr(device, "disk"):
            name += ",%d" % (device.parted_partition.number - 1,)
        name += ")"
        return name

    @property
    def grub_config_dir(self):
        """ Config dir, adjusted for grub's view of the world. """
        return self.boot_prefix + self._config_dir

    #
    # configuration
    #

    @property
    def config_dir(self):
        """ Full path to configuration directory. """
        return "/boot/" + self._config_dir

    @property
    def config_file(self):
        """ Full path to configuration file. """
        return "%s/%s" % (self.config_dir, self._config_file)

    @property
    def device_map_file(self):
        """ Full path to device.map file. """
        return "%s/%s" % (self.config_dir, self._device_map_file)

    @property
    def grub_conf_device_line(self):
        return ""

    @property
    def splash_dir(self):
        """ relative path to splash image directory."""
        return GRUB._config_dir

    @property
    def has_serial_console(self):
        """ true if the console is a serial console. """

        return any(self.console.startswith(sconsole) for sconsole in self._serial_consoles)

    @property
    def serial_command(self):
        command = ""
        if self.console and self.has_serial_console:
            unit = self.console[-1]
            command = ["serial"]
            s = _parse_serial_opt(self.console_options)
            if unit and unit != '0':
                command.append("--unit=%s" % unit)
            if s.speed and s.speed != '9600':
                command.append("--speed=%s" % s.speed)
            if s.parity:
                if s.parity == 'o':
                    command.append("--parity=odd")
                elif s.parity == 'e':
                    command.append("--parity=even")
            if s.word and s.word != '8':
                command.append("--word=%s" % s.word)
            if s.stop and s.stop != '1':
                command.append("--stop=%s" % s.stop)
            command = " ".join(command)
        return command

    def write_config_console(self, config):
        """ Write console-related configuration. """
        if not self.console:
            return

        if self.has_serial_console:
            config.write("%s\n" % self.serial_command)
            config.write("terminal --timeout=%s serial console\n"
                         % self.timeout)

        console_arg = "console=%s" % self.console
        if self.console_options:
            console_arg += ",%s" % self.console_options
        self.boot_args.add(console_arg)

    def _encrypt_password(self):
        """ Make sure self.encrypted_password is set up correctly. """
        if self.encrypted_password:
            return

        if not self.password:
            raise BootLoaderError("cannot encrypt empty password")

        # Encrypt using sha512 and 16 character salt
        self.encrypted_password = crypt.crypt(self.password, crypt.METHOD_SHA512)

    def write_config_password(self, config):
        """ Write password-related configuration. """
        if not self.password and not self.encrypted_password:
            return

        self._encrypt_password()
        password_line = "--encrypted " + self.encrypted_password
        config.write("password %s\n" % password_line)

    def write_config_header(self, config):
        """Write global configuration information. """
        if self.boot_prefix:
            have_boot = "do not "
        else:
            have_boot = ""

        s = """# grub.conf generated by anaconda
# Note that you do not have to rerun grub after making changes to this file.
# NOTICE:  You %(do)shave a /boot partition. This means that all kernel and
#          initrd paths are relative to %(boot)s, eg.
#          root %(grub_target)s
#          kernel %(prefix)s/vmlinuz-version ro root=%(root_device)s
#          initrd %(prefix)s/initrd-[generic-]version.img
""" % {"do": have_boot, "boot": self.stage2_device.format.mountpoint,
       "root_device": self.stage2_device.path,
       "grub_target": self.grub_device_name(self.stage1_device),
       "prefix": self.boot_prefix}

        config.write(s)
        config.write("boot=%s\n" % self.stage1_device.path)
        config.write(self.grub_conf_device_line)

        # find the index of the default image
        try:
            default_index = self.images.index(self.default)
        except ValueError:
            # pylint: disable=no-member
            e = "Failed to find default image (%s)" % self.default.label
            raise BootLoaderError(e)

        config.write("default=%d\n" % default_index)
        config.write("timeout=%d\n" % self.timeout)

        self.write_config_console(config)

        if util.isConsoleOnVirtualTerminal(self.console):
            splash = "splash.xpm.gz"
            splash_path = os.path.normpath("%s/boot/%s/%s" % (util.getSysroot(),
                                                              self.splash_dir,
                                                              splash))
            if os.access(splash_path, os.R_OK):
                grub_root_grub_name = self.grub_device_name(self.stage2_device)
                config.write("splashimage=%s/%s/%s\n" % (grub_root_grub_name,
                                                         self.splash_dir,
                                                         splash))
                config.write("hiddenmenu\n")

        self.write_config_password(config)

    def write_config_images(self, config):
        """ Write image entries into configuration file. """
        for image in self.images:
            args = Arguments()
            if isinstance(image, LinuxBootLoaderImage):
                grub_root = self.grub_device_name(self.stage2_device)
                args.update(["ro", "root=%s" % image.device.fstab_spec])
                args.update(self.boot_args)
                if isinstance(image, TbootLinuxBootLoaderImage):
                    args.update(image.args)
                    snippet = ("\tkernel %(prefix)s/%(multiboot)s %(mbargs)s\n"
                               "\tmodule %(prefix)s/%(kernel)s %(args)s\n"
                               "\tmodule %(prefix)s/%(initrd)s\n"
                               % {"prefix": self.boot_prefix,
                                  "multiboot": image.multiboot,
                                  "mbargs": image.mbargs,
                                  "kernel": image.kernel, "args": args,
                                  "initrd": image.initrd})
                else:
                    snippet = ("\tkernel %(prefix)s/%(kernel)s %(args)s\n"
                               "\tinitrd %(prefix)s/%(initrd)s\n"
                               % {"prefix": self.boot_prefix,
                                  "kernel": image.kernel, "args": args,
                                  "initrd": image.initrd})
                stanza = ("title %(label)s (%(version)s)\n"
                          "\troot %(grub_root)s\n"
                          "%(snippet)s"
                          % {"label": image.label, "version": image.version,
                             "grub_root": grub_root, "snippet": snippet})
            else:
                stanza = ("title %(label)s\n"
                          "\trootnoverify %(grub_root)s\n"
                          "\tchainloader +1\n"
                          % {"label": image.label,
                             "grub_root": self.grub_device_name(image.device)})

            log.info("bootloader.py: used boot args: %s ", args)
            config.write(stanza)

    def write_device_map(self):
        """ Write out a device map containing all supported devices. """
        map_path = os.path.normpath(util.getSysroot() + self.device_map_file)
        if os.access(map_path, os.R_OK):
            os.rename(map_path, map_path + ".anacbak")

        dev_map = open(map_path, "w")
        dev_map.write("# this device map was generated by anaconda\n")
        for disk in self.disks:
            dev_map.write("%s      %s\n" % (self.grub_device_name(disk),
                                            disk.path))
        dev_map.close()

    def write_config_post(self):
        """ Perform additional configuration after writing config file(s). """
        super().write_config_post()

        # make symlink for menu.lst (grub's default config file name)
        menu_lst = "%s%s/menu.lst" % (util.getSysroot(), self.config_dir)
        if os.access(menu_lst, os.R_OK):
            try:
                os.rename(menu_lst, menu_lst + '.anacbak')
            except OSError as e:
                log.error("failed to back up %s: %s", menu_lst, e)

        try:
            os.symlink(self._config_file, menu_lst)
        except OSError as e:
            log.error("failed to create grub menu.lst symlink: %s", e)

        # make symlink to grub.conf in /etc since that's where configs belong
        etc_grub = "%s/etc/%s" % (util.getSysroot(), self._config_file)
        if os.access(etc_grub, os.R_OK):
            try:
                os.unlink(etc_grub)
            except OSError as e:
                log.error("failed to remove %s: %s", etc_grub, e)

        try:
            os.symlink("..%s" % self.config_file, etc_grub)
        except OSError as e:
            log.error("failed to create /etc/grub.conf symlink: %s", e)

    def write_config(self):
        """ Write bootloader configuration to disk. """
        # write device.map
        self.write_device_map()

        # this writes the actual configuration file
        super().write_config()

    #
    # installation
    #

    @property
    def install_targets(self):
        """ List of (stage1, stage2) tuples representing install targets. """
        targets = []

        # make sure we have stage1 and stage2 installed with redundancy
        # so that boot can succeed even in the event of failure or removal
        # of some of the disks containing the member partitions of the
        # /boot array. If the stage1 is not a disk, it probably needs to
        # be a partition on a particular disk (biosboot, prepboot), so only
        # add the redundant targets if installing stage1 to a disk that is
        # a member of the stage2 array.

        # Look for both mdraid and btrfs raid
        if self.stage2_device.type == "mdarray" and \
           self.stage2_device.level in self.stage2_raid_levels:
            stage2_raid = True
            # Set parents to the list of partitions in the RAID
            stage2_parents = self.stage2_device.parents
        elif self.stage2_device.type == "btrfs subvolume" and \
           self.stage2_device.parents[0].data_level in self.stage2_raid_levels:
            stage2_raid = True
            # Set parents to the list of partitions in the parent volume
            stage2_parents = self.stage2_device.parents[0].parents
        else:
            stage2_raid = False

        if stage2_raid and \
           self.stage1_device.is_disk and \
           self.stage2_device.depends_on(self.stage1_device):
            for stage2dev in stage2_parents:
                # if target disk contains any of /boot array's member
                # partitions, set up stage1 on each member's disk
                stage1dev = stage2dev.disk
                targets.append((stage1dev, self.stage2_device))
        else:
            targets.append((self.stage1_device, self.stage2_device))

        return targets

    def install(self, args=None):
        rc = util.execInSysroot("grub-install", ["--just-copy"])
        if rc:
            raise BootLoaderError("boot loader install failed")

        for (stage1dev, stage2dev) in self.install_targets:
            cmd = ("root %(stage2dev)s\n"
                   "install --stage2=%(config_dir)s/stage2"
                   " /%(grub_config_dir)s/stage1 d %(stage1dev)s"
                   " /%(grub_config_dir)s/stage2 p"
                   " %(stage2dev)s/%(grub_config_dir)s/%(config_basename)s\n"
                   % {"grub_config_dir": self.grub_config_dir,
                      "config_dir": self.config_dir,
                      "config_basename": self._config_file,
                      "stage1dev": self.grub_device_name(stage1dev),
                      "stage2dev": self.grub_device_name(stage2dev)})
            (pread, pwrite) = os.pipe()
            os.write(pwrite, cmd.encode("utf-8"))
            os.close(pwrite)
            args = ["--batch", "--no-floppy",
                    "--device-map=%s" % self.device_map_file]
            rc = util.execInSysroot("grub", args, stdin=pread)
            os.close(pread)
            if rc:
                raise BootLoaderError("boot loader install failed")

    def update(self):
        self.install()

    #
    # miscellaneous
    #

    def has_windows(self, devices):
        """ Potential boot devices containing non-linux operating systems. """
        # make sure we don't clobber error/warning lists
        errors = self.errors[:]
        warnings = self.warnings[:]
        ret = [d for d in devices if self.is_valid_stage2_device(d, linux=False, non_linux=True)]
        self.errors = errors
        self.warnings = warnings
        return bool(ret)

    # Add a warning about certain RAID situations to is_valid_stage2_device
    def is_valid_stage2_device(self, device, linux=True, non_linux=False):
        valid = super().is_valid_stage2_device(device, linux, non_linux)

        # If the stage2 device is on a raid1, check that the stage1 device is also redundant,
        # either by also being part of an array or by being a disk (which is expanded
        # to every disk in the array by install_targets).
        if self.stage1_device and self.stage2_device and \
                self.stage2_device.type == "mdarray" and \
                self.stage2_device.level in self.stage2_raid_levels and \
                self.stage1_device.type != "mdarray":
            if not self.stage1_device.is_disk:
                msg = _("boot loader stage2 device %(stage2dev)s is on a multi-disk array, "
                        "but boot loader stage1 device %(stage1dev)s is not. "
                        "A drive failure in %(stage2dev)s could render the system unbootable.") % \
                        {"stage1dev": self.stage1_device.name,
                         "stage2dev": self.stage2_device.name}
                self.warnings.append(msg)
            elif not self.stage2_device.depends_on(self.stage1_device):
                msg = _("boot loader stage2 device %(stage2dev)s is on a multi-disk array, "
                        "but boot loader stage1 device %(stage1dev)s is not part of this array. "
                        "The stage1 boot loader will only be installed to a single drive.") % \
                        {"stage1dev": self.stage1_device.name,
                         "stage2dev": self.stage2_device.name}
                self.warnings.append(msg)

        return valid
