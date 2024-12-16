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
import os
import re
from _ped import PARTITION_BIOS_GRUB  # pylint: disable=no-name-in-module

from blivet.devicelibs import raid

from pyanaconda.modules.storage.bootloader.base import BootLoader, BootLoaderError
from pyanaconda.core import util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.i18n import _
from pyanaconda.core.path import open_with_perm
from pyanaconda.core.product import get_product_name

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["GRUB2", "IPSeriesGRUB2"]


class SerialConsoleOptions:
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


class GRUB2(BootLoader):
    """GRUBv2.

    - configuration
        - password (insecure), password_pbkdf2
          http://www.gnu.org/software/grub/manual/grub.html#Invoking-grub_002dmkpasswd_002dpbkdf2
        - users per-entry specifies which users can access, otherwise entry is unrestricted
        - /etc/grub/custom.cfg

    - how does grub resolve names of md arrays?

    - disable automatic use of grub-mkconfig?
        - on upgrades?

    - BIOS boot partition (GPT)
        - parted /dev/sda set <partition_number> bios_grub on
        - can't contain a file system
        - 31KiB min, 1MiB recommended
    """
    name = "GRUB2"
    # grub2 is a virtual provides that's provided by grub2-pc, grub2-ppc64le,
    # and all of the primary grub components that aren't grub2-efi-${EFIARCH}
    packages = ["grub2", "grub2-tools"]
    _config_file = "grub.cfg"
    _config_dir = "grub2"
    _passwd_file = "user.cfg"
    defaults_file = "/etc/default/grub"
    terminal_type = "console"
    stage2_max_end = None

    _device_map_file = "device.map"

    stage2_is_valid_stage1 = True
    stage2_bootable = True
    stage2_must_be_primary = False

    # requirements for boot devices
    stage2_device_types = ["partition", "mdarray", "btrfs volume", "btrfs subvolume"]
    stage2_raid_levels = [raid.RAID0, raid.RAID1, raid.RAID4,
                          raid.RAID5, raid.RAID6, raid.RAID10]
    stage2_raid_member_types = ["partition"]
    stage2_raid_metadata = ["0", "0.90", "1.0", "1.2"]

    _serial_consoles = ["ttyS"]

    # XXX we probably need special handling for raid stage1 w/ gpt disklabel
    #     since it's unlikely there'll be a bios boot partition on each disk

    def __init__(self):
        super().__init__()
        self.encrypted_password = ""

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

    def write_config_images(self, config):
        return True

    @property
    def stage2_format_types(self):
        if get_product_name().startswith("Red Hat "): # pylint: disable=no-member
            return ["xfs", "ext4", "ext3", "ext2"]
        else:
            return ["ext4", "ext3", "ext2", "btrfs", "xfs"]

    #
    # grub-related conveniences
    #

    def grub_device_name(self, device):
        """Return a grub-friendly representation of device.

        Disks and partitions use the (hdX,Y) notation, while lvm and
        md devices just use their names.
        """
        disk = None
        name = "(%s)" % device.name

        if device.is_disk:
            disk = device
        elif hasattr(device, "disk"):
            disk = device.disk

        if disk is not None:
            name = "(hd%d" % self.disks.index(disk)
            if hasattr(device, "disk"):
                lt = device.disk.format.label_type
                name += ",%s%d" % (lt, device.parted_partition.number)
            name += ")"
        return name

    def write_config_console(self, config):
        if not self.console:
            return

        console_arg = "console=%s" % self.console
        if self.console_options:
            console_arg += ",%s" % self.console_options
        self.boot_args.add(console_arg)

    def write_device_map(self):
        """Write out a device map containing all supported devices."""
        map_path = os.path.normpath(conf.target.system_root + self.device_map_file)
        if os.access(map_path, os.R_OK):
            os.rename(map_path, map_path + ".anacbak")

        devices = self.disks
        if self.stage1_device not in devices:
            devices.append(self.stage1_device)

        for disk in self.stage2_device.disks:
            if disk not in devices:
                devices.append(disk)

        devices = [d for d in devices if d.is_disk]

        if len(devices) == 0:
            return

        dev_map = open(map_path, "w")
        dev_map.write("# this device map was generated by anaconda\n")
        for drive in devices:
            dev_map.write("%s      %s\n" % (self.grub_device_name(drive),
                                            drive.path))
        dev_map.close()

    def write_defaults(self):
        defaults_file = "%s%s" % (conf.target.system_root, self.defaults_file)
        defaults = open(defaults_file, "w+")
        defaults.write("GRUB_TIMEOUT=%d\n" % self.timeout)
        defaults.write("GRUB_DISTRIBUTOR=\"$(sed 's, release .*$,,g' /etc/system-release)\"\n")
        defaults.write("GRUB_DEFAULT=saved\n")
        defaults.write("GRUB_DISABLE_SUBMENU=true\n")
        if self.console and self.has_serial_console:
            defaults.write("GRUB_TERMINAL=\"serial console\"\n")
            defaults.write("GRUB_SERIAL_COMMAND=\"%s\"\n" % self.serial_command)
        else:
            defaults.write("GRUB_TERMINAL_OUTPUT=\"%s\"\n" % self.terminal_type)

        # this is going to cause problems for systems containing multiple
        # linux installations or even multiple boot entries with different
        # boot arguments
        log.info("bootloader.py: used boot args: %s ", self.boot_args)
        defaults.write("GRUB_CMDLINE_LINUX=\"%s\"\n" % self.boot_args)
        defaults.write("GRUB_DISABLE_RECOVERY=\"true\"\n")
        #defaults.write("GRUB_THEME=\"/boot/grub2/themes/system/theme.txt\"\n")

        if self.use_bls and os.path.exists(conf.target.system_root + "/usr/sbin/new-kernel-pkg"):
            log.warning("BLS support disabled due new-kernel-pkg being present")
            self.use_bls = False

        hv_type_path = "/sys/hypervisor/type"
        if self.use_bls and os.access(hv_type_path, os.F_OK):
            with open(hv_type_path, "r") as fd:
                if fd.readline().strip() == "xen":
                    log.warning("BLS support disabled because is a Xen machine")
                    self.use_bls = False

        if self.use_bls:
            defaults.write("GRUB_ENABLE_BLSCFG=true\n")
        defaults.close()

    def _encrypt_password(self):
        """Make sure self.encrypted_password is set up properly."""
        if self.encrypted_password:
            return

        if not self.password:
            raise RuntimeError("cannot encrypt empty password")

        (pread, pwrite) = os.pipe()
        passwords = "%s\n%s\n" % (self.password, self.password)
        os.write(pwrite, passwords.encode("utf-8"))
        os.close(pwrite)
        buf = util.execWithCapture("grub2-mkpasswd-pbkdf2", [],
                                   stdin=pread,
                                   root=conf.target.system_root)
        os.close(pread)
        self.encrypted_password = buf.split()[-1].strip()
        if not self.encrypted_password.startswith("grub.pbkdf2."):
            raise BootLoaderError("failed to encrypt boot loader password")

    def write_password_config(self):
        if not self.password and not self.encrypted_password:
            return

        users_file = "%s%s/%s" % (conf.target.system_root, self.config_dir, self._passwd_file)
        header = open_with_perm(users_file, "w", 0o600)
        # XXX FIXME: document somewhere that the username is "root"
        self._encrypt_password()
        password_line = "GRUB2_PASSWORD=" + self.encrypted_password
        header.write("%s\n" % password_line)
        header.close()

    def write_config(self):
        self.write_config_console(None)
        # See if we have a password and if so update the boot args before we
        # write out the defaults file.
        if self.password or self.encrypted_password:
            self.boot_args.add("rd.shell=0")
        self.write_defaults()

        # if we fail to setup password auth we should complete the
        # installation so the system is at least bootable
        try:
            self.write_password_config()
        except (BootLoaderError, OSError, RuntimeError) as e:
            log.error("boot loader password setup failed: %s", e)

        # make sure the default entry is the OS we are installing
        if self.default is not None:
            machine_id_path = conf.target.system_root + "/etc/machine-id"
            if not os.access(machine_id_path, os.R_OK):
                log.error("failed to read machine-id, default entry not set")
                return

            with open(machine_id_path, "r") as fd:
                machine_id = fd.readline().strip()

            default_entry = "%s-%s" % (machine_id, self.default.version)
            rc = util.execWithRedirect(
                "grub2-set-default",
                [default_entry],
                root=conf.target.system_root
            )
            if rc:
                log.error("failed to set default menu entry to %s", get_product_name())

        # set menu_auto_hide grubenv variable if we should enable menu_auto_hide
        # set boot_success so that the menu is hidden on the boot after install
        if conf.bootloader.menu_auto_hide:
            rc = util.execWithRedirect(
                "grub2-editenv",
                ["-", "set", "menu_auto_hide=1", "boot_success=1"],
                root=conf.target.system_root
            )
            if rc:
                log.error("failed to set menu_auto_hide=1")

        # now tell grub2 to generate the main configuration file
        rc = util.execWithRedirect(
            "grub2-mkconfig",
            ["-o", self.config_file],
            root=conf.target.system_root
        )
        if rc:
            raise BootLoaderError("failed to write boot loader configuration")

    #
    # installation
    #

    @property
    def install_targets(self):
        """ List of (stage1, stage2) tuples representing install targets. """
        # make sure we have stage1 and stage2 installed with redundancy
        # so that boot can succeed even in the event of failure or removal
        # of some of the disks containing the member partitions of the
        # /boot array. If the stage1 is not a disk, it probably needs to
        # be a partition on a particular disk (biosboot, prepboot), so only
        # add the redundant targets if installing stage1 to a disk that is
        # a member of the stage2 array.
        stage2_parents = []

        if self.stage1_device \
                and self.stage2_device \
                and self.stage1_device.is_disk \
                and self.stage2_device.depends_on(self.stage1_device):

            # Look for both mdraid and btrfs raid
            if self.stage2_device.type == "mdarray" and \
                    self.stage2_device.level in self.stage2_raid_levels:
                # Set parents to the list of partitions in the RAID
                stage2_parents = self.stage2_device.parents

            elif self.stage2_device.type == "btrfs subvolume" and \
                    self.stage2_device.parents[0].data_level in self.stage2_raid_levels:
                # Set parents to the list of partitions in the parent volume
                stage2_parents = self.stage2_device.parents[0].parents

        if stage2_parents:
            # If target disk contains any of /boot array's member
            # partitions, set up stage1 on each member's disk.
            return [(d.disk, self.stage2_device) for d in stage2_parents]

        return super().install_targets

    def install(self, args=None):
        if args is None:
            args = []

        # XXX will installing to multiple drives work as expected with GRUBv2?
        for (stage1dev, stage2dev) in self.install_targets:
            grub_args = args + ["--no-floppy", stage1dev.path]
            if stage1dev == stage2dev:
                # This is hopefully a temporary hack. GRUB2 currently refuses
                # to install to a partition's boot block without --force.
                grub_args.insert(0, '--force')
            else:
                if self.keep_mbr:
                    grub_args.insert(0, '--grub-setup=/bin/true')
                    log.info("bootloader.py: mbr update by grub2 disabled")
                else:
                    log.info("bootloader.py: mbr will be updated for grub2")

            rc = util.execWithRedirect("grub2-install", grub_args,
                                       root=conf.target.system_root,
                                       env_prune=['MALLOC_PERTURB_'])
            if rc:
                raise BootLoaderError("boot loader install failed")

    def write(self):
        """Write the bootloader configuration and install the bootloader."""
        if self.skip_bootloader:
            return

        try:
            self.write_device_map()
            self.stage2_device.format.sync(root=conf.target.physical_root)
            os.sync()
            self.install()
            os.sync()
            self.stage2_device.format.sync(root=conf.target.physical_root)
        finally:
            self.write_config()
            os.sync()
            self.stage2_device.format.sync(root=conf.target.physical_root)

    def check(self):
        """When installing to the mbr of a disk grub2 needs enough space
        before the first partition in order to embed its core.img

        Until we have a way to ask grub2 what the size is we check to make
        sure it starts >= 512K, otherwise return an error.
        """
        ret = True
        base_gap_bytes = 32256       # 31.5KiB
        advanced_gap_bytes = 524288  # 512KiB
        self.errors = []
        self.warnings = []

        if self.stage1_device == self.stage2_device:
            return ret

        # These are small enough to fit
        if self.stage2_device.type == "partition":
            min_start = base_gap_bytes
        else:
            min_start = advanced_gap_bytes

        if not self.stage1_disk:
            return False

        # If the first partition starts too low and there is no biosboot partition show an error.
        error_msg = None
        biosboot = False
        for p in self.stage1_disk.children:
            if p.format.type == "biosboot" or p.parted_partition.getFlag(PARTITION_BIOS_GRUB):
                biosboot = True
                break

            start = p.parted_partition.geometry.start * p.parted_partition.disk.device.sectorSize
            if start < min_start:
                error_msg = _("%(deviceName)s may not have enough space for grub2 to embed "
                              "core.img when using the %(fsType)s file system on %(deviceType)s") \
                              % {"deviceName": self.stage1_device.name,
                                 "fsType": self.stage2_device.format.type,
                                 "deviceType": self.stage2_device.type}

        if error_msg and not biosboot:
            log.error(error_msg)
            self.errors.append(error_msg)
            ret = False

        return ret

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


class IPSeriesGRUB2(GRUB2):
    """IPSeries GRUBv2"""

    # GRUB2 sets /boot bootable and not the PReP partition. This causes the Open Firmware BIOS
    # not to present the disk as a bootable target. If stage2_bootable is False, then the PReP
    # partition will be marked bootable. Confusing.

    stage2_bootable = False
    terminal_type = "ofconsole"

    #
    # installation
    #

    def install(self, args=None):
        if self.keep_boot_order:
            log.info("leavebootorder passed as an option. Will not update the NVRAM boot list.")
        else:
            self.updateNVRAMBootList()

        super().install(args=["--no-nvram"])

    # This will update the PowerPC's (ppc) bios boot devive order list
    def updateNVRAMBootList(self):
        if not conf.target.is_hardware:
            return

        log.debug("updateNVRAMBootList: self.stage1_device.path = %s", self.stage1_device.path)

        rc = util.execWithRedirect("bootlist",
                                   ["-m", "normal", "-o", self.stage1_device.path])
        if rc:
            log.error("Failed to update new boot device order")

    #
    # In addition to the normal grub configuration variable, add one more to set the size
    # of the console's window to a standard 80x24
    #
    def write_defaults(self):
        super().write_defaults()

        defaults_file = "%s%s" % (conf.target.system_root, self.defaults_file)
        defaults = open(defaults_file, "a+")
        # The terminfo's X and Y size, and output location could change in the future
        defaults.write("GRUB_TERMINFO=\"terminfo -g 80x24 console\"\n")
        # Disable OS Prober on pSeries systems
        # TODO: This will disable across all POWER platforms. Need to get
        #       into blivet and rework how it segments the POWER systems
        #       to allow for differentiation between PowerNV and
        #       PowerVM / POWER on qemu/kvm
        defaults.write("GRUB_DISABLE_OS_PROBER=true\n")
        defaults.close()


class PowerNVGRUB2(GRUB2):
    """PowerNV GRUBv2"""

    def install(self, args=None):
        """installation should be a no-op, just writing the config is sufficient for the
        firmware's bootloader (petitboot)
        """
        pass
