#
# Copyright (C) 2011 Red Hat, Inc.
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
from glob import glob

from pyanaconda.core import util
from blivet.devicelibs import raid

from pyanaconda.bootloader.base import BootLoaderError, Arguments, BootLoader
from pyanaconda.bootloader.grub import GRUB
from pyanaconda.bootloader.image import LinuxBootLoaderImage, TbootLinuxBootLoaderImage
from pyanaconda.core.constants import BOOTLOADER_TYPE_EXTLINUX
from pyanaconda.modules.common.constants.objects import BOOTLOADER
from pyanaconda.modules.common.constants.services import STORAGE
from pyanaconda.product import productName
from pyanaconda.flags import flags
from pyanaconda.errors import errorHandler, ERROR_RAISE, ZIPLError
from pyanaconda import platform
from pyanaconda.core.i18n import _
from pyanaconda.core.configuration.anaconda import conf

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)


class GRUB2(GRUB):
    """ GRUBv2

        - configuration
            - password (insecure), password_pbkdf2
                - http://www.gnu.org/software/grub/manual/grub.html#Invoking-grub_002dmkpasswd_002dpbkdf2
            - --users per-entry specifies which users can access, otherwise
              entry is unrestricted
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

    # requirements for boot devices
    stage2_device_types = ["partition", "mdarray"]
    stage2_raid_levels = [raid.RAID0, raid.RAID1, raid.RAID4,
                          raid.RAID5, raid.RAID6, raid.RAID10]
    stage2_raid_metadata = ["0", "0.90", "1.0", "1.2"]

    # XXX we probably need special handling for raid stage1 w/ gpt disklabel
    #     since it's unlikely there'll be a bios boot partition on each disk

    @property
    def stage2_format_types(self):
        if productName.startswith("Red Hat "):              # pylint: disable=no-member
            return ["xfs", "ext4", "ext3", "ext2"]
        else:
            return ["ext4", "ext3", "ext2", "btrfs", "xfs"]

    #
    # grub-related conveniences
    #

    def grub_device_name(self, device):
        """ Return a grub-friendly representation of device.

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
        """ Write out a device map containing all supported devices. """
        map_path = os.path.normpath(util.getSysroot() + self.device_map_file)
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
        defaults_file = "%s%s" % (util.getSysroot(), self.defaults_file)
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

        if self.use_bls and os.path.exists(util.getSysroot() + "/usr/sbin/new-kernel-pkg"):
            log.warning("BLS support disabled due new-kernel-pkg being present")
            self.use_bls = False

        if self.use_bls:
            defaults.write("GRUB_ENABLE_BLSCFG=true\n")
        defaults.close()

    def _encrypt_password(self):
        """ Make sure self.encrypted_password is set up properly. """
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
                                   root=util.getSysroot())
        os.close(pread)
        self.encrypted_password = buf.split()[-1].strip()
        if not self.encrypted_password.startswith("grub.pbkdf2."):
            raise BootLoaderError("failed to encrypt boot loader password")

    def write_password_config(self):
        if not self.password and not self.encrypted_password:
            return

        users_file = "%s%s/%s" % (util.getSysroot(), self.config_dir, self._passwd_file)
        header = util.open_with_perm(users_file, "w", 0o700)
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
            # find the index of the default image
            try:
                default_index = self.images.index(self.default)
            except ValueError:
                # pylint: disable=no-member
                log.warning("Failed to find default image (%s), defaulting to 0", self.default.label)
                default_index = 0

            rc = util.execInSysroot("grub2-set-default", [str(default_index)])
            if rc:
                log.error("failed to set default menu entry to %s", productName)

        # set menu_auto_hide grubenv variable if we should enable menu_auto_hide
        # set boot_success so that the menu is hidden on the boot after install
        if self.menu_auto_hide:
            rc = util.execInSysroot("grub2-editenv",
                                    ["-", "set", "menu_auto_hide=1",
                                     "boot_success=1"])
            if rc:
                log.error("failed to set menu_auto_hide=1")

        # now tell grub2 to generate the main configuration file
        rc = util.execInSysroot("grub2-mkconfig",
                                ["-o", self.config_file])
        if rc:
            raise BootLoaderError("failed to write boot loader configuration")

    #
    # installation
    #

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
                                       root=util.getSysroot(),
                                       env_prune=['MALLOC_PERTURB_'])
            if rc:
                raise BootLoaderError("boot loader install failed")

    def write(self):
        """ Write the bootloader configuration and install the bootloader. """
        if self.skip_bootloader:
            return

        if self.update_only:
            self.update()
            return

        try:
            self.write_device_map()
            self.stage2_device.format.sync(root=util.getTargetPhysicalRoot())
            os.sync()
            self.install()
            os.sync()
            self.stage2_device.format.sync(root=util.getTargetPhysicalRoot())
        finally:
            self.write_config()
            os.sync()
            self.stage2_device.format.sync(root=util.getTargetPhysicalRoot())

    def check(self):
        """ When installing to the mbr of a disk grub2 needs enough space
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
        parts = self.stage1_disk.format.parted_disk.partitions
        for p in parts:
            if p.getFlag(PARTITION_BIOS_GRUB):
                biosboot = True
                break

            start = p.geometry.start * p.disk.device.sectorSize
            if start < min_start:
                error_msg = _("%(deviceName)s may not have enough space for grub2 to embed "
                              "core.img when using the %(fsType)s file system on %(deviceType)s") \
                              % {"deviceName": self.stage1_device.name, "fsType": self.stage2_device.format.type,
                                 "deviceType": self.stage2_device.type}

        if error_msg and not biosboot:
            log.error(error_msg)
            self.errors.append(error_msg)
            ret = False

        return ret

class EFIBase(object):

    def __init__(self):
        super().__init__()
        self.efi_dir = None

    @property
    def _config_dir(self):
        return "efi/EFI/{}".format(self.efi_dir)

    def efibootmgr(self, *args, **kwargs):
        if not conf.target.is_hardware:
            log.info("Skipping efibootmgr for image/directory install.")
            return ""

        if "noefi" in flags.cmdline:
            log.info("Skipping efibootmgr for noefi")
            return ""

        if kwargs.pop("capture", False):
            exec_func = util.execWithCapture
        else:
            exec_func = util.execWithRedirect
        if "root" not in kwargs:
            kwargs["root"] = util.getSysroot()

        return exec_func("efibootmgr", list(args), **kwargs)

    @property
    def efi_dir_as_efifs_dir(self):
        ret = self._config_dir.replace('efi/', '')
        return "\\" + ret.replace('/', '\\')

    def _add_single_efi_boot_target(self, partition):
        boot_disk = partition.disk
        boot_part_num = str(partition.parted_partition.number)

        rc = self.efibootmgr(
            "-c", "-w", "-L", productName.split("-")[0],  # pylint: disable=no-member
            "-d", boot_disk.path, "-p", boot_part_num,
            "-l", self.efi_dir_as_efifs_dir + self._efi_binary,  # pylint: disable=no-member
            root=util.getSysroot()
        )
        if rc:
            raise BootLoaderError("failed to set new efi boot target. This is most likely a kernel or firmware bug.")

    def add_efi_boot_target(self):
        if self.stage1_device.type == "partition":  # pylint: disable=no-member
            self._add_single_efi_boot_target(self.stage1_device)  # pylint: disable=no-member
        elif self.stage1_device.type == "mdarray":  # pylint: disable=no-member
            for parent in self.stage1_device.parents:  # pylint: disable=no-member
                self._add_single_efi_boot_target(parent)

    def remove_efi_boot_target(self):
        buf = self.efibootmgr(capture=True)
        for line in buf.splitlines():
            try:
                (slot, _product) = line.split(None, 1)
            except ValueError:
                continue

            if _product == productName.split("-")[0]:           # pylint: disable=no-member
                slot_id = slot[4:8]
                # slot_id is hex, we can't use .isint and use this regex:
                if not re.match("^[0-9a-fA-F]+$", slot_id):
                    log.warning("failed to parse efi boot slot (%s)", slot)
                    continue

                rc = self.efibootmgr("-b", slot_id, "-B")
                if rc:
                    raise BootLoaderError("failed to remove old efi boot entry.  This is most likely a kernel or firmware bug.")

    def update(self):
        self.install()

    def write(self):
        """ Write the bootloader configuration and install the bootloader. """
        if self.skip_bootloader:  # pylint: disable=no-member
            return

        if self.update_only:  # pylint: disable=no-member
            self.update()
            return

        try:
            os.sync()
            self.stage2_device.format.sync(root=util.getTargetPhysicalRoot()) # pylint: disable=no-member
            self.install()
        finally:
            self.write_config()  # pylint: disable=no-member

    def check(self):
        return True

    def install(self, args=None):
        if not self.keep_boot_order:  # pylint: disable=no-member
            self.remove_efi_boot_target()
        self.add_efi_boot_target()


class EFIGRUB1(EFIBase, GRUB):
    packages = ["efibootmgr"]
    can_dual_boot = False

    # list of strings representing options for boot device types
    stage2_device_types = ["partition"]
    stage2_raid_levels = []
    stage2_raid_member_types = []
    stage2_raid_metadata = []

    stage2_is_valid_stage1 = False
    stage2_bootable = False

    _efi_binary = "\\grub.efi"

    def __init__(self):
        super().__init__()
        self.efi_dir = 'BOOT'

    #
    # configuration
    #

    @property
    def efi_product_path(self):
        """ The EFI product path.

            eg: HD(1,800,64000,faacb4ef-e361-455e-bd97-ca33632550c3)
        """
        buf = self.efibootmgr("-v", capture=True)
        matches = re.search(productName + r'\s+(HD\(.+?\))', buf)
        if matches and matches.groups():
            return matches.group(1)
        return ""

    @property
    def grub_conf_device_line(self):
        return "device %s %s\n" % (self.grub_device_name(self.stage2_device),
                                   self.efi_product_path)


class EFIGRUB(EFIBase, GRUB2):
    _packages32 = [ "grub2-efi-ia32", "shim-ia32" ]
    _packages_common = [ "efibootmgr" ]
    can_dual_boot = False
    stage2_is_valid_stage1 = False
    stage2_bootable = False

    _is_32bit_firmware = False

    def __init__(self):
        super().__init__()
        self.efi_dir = 'BOOT'
        self._packages64 = [ "grub2-efi-x64", "shim-x64" ]

        try:
            f = open("/sys/firmware/efi/fw_platform_size", "r")
            value = f.readline().strip()
        except IOError:
            log.info("Reading /sys/firmware/efi/fw_platform_size failed, defaulting to 64-bit install.")
            value = '64'
        if value == '32':
            self._is_32bit_firmware = True

    @property
    def _efi_binary(self):
        if self._is_32bit_firmware:
            return "\\shimia32.efi"
        return "\\shimx64.efi"

    @property
    def packages(self):
        if self._is_32bit_firmware:
            return self._packages32 + self._packages_common + \
                super().packages
        return self._packages64 + self._packages_common + \
            super().packages

class Aarch64EFIGRUB(EFIGRUB):
    _serial_consoles = ["ttyAMA", "ttyS"]
    _efi_binary = "\\shimaa64.efi"

    def __init__(self):
        super().__init__()
        self._packages64 = ["grub2-efi-aa64", "shim-aa64"]

class ArmEFIGRUB(EFIGRUB):
    _serial_consoles = ["ttyAMA", "ttyS"]
    _efi_binary = "\\grubarm.efi"

    def __init__(self):
        super().__init__()
        self._packages32 = ["grub2-efi-arm"]
        self._is_32bit_firmware = True

class MacEFIGRUB(EFIGRUB):
    def __init__(self):
        super().__init__()
        self._packages64.extend(["grub2-tools-efi", "mactel-boot"])

    def mactel_config(self):
        if os.path.exists(util.getSysroot() + "/usr/libexec/mactel-boot-setup"):
            rc = util.execInSysroot("/usr/libexec/mactel-boot-setup", [])
            if rc:
                log.error("failed to configure Mac boot loader")

    def install(self, args=None):
        super().install()
        self.mactel_config()

    def is_valid_stage1_device(self, device, early=False):
        valid = super().is_valid_stage1_device(device, early)

        # Make sure we don't pick the OSX root partition
        if valid and getattr(device.format, "name", "") != "Linux HFS+ ESP":
            valid = False

        if hasattr(device.format, "name"):
            log.debug("device.format.name is '%s'", device.format.name)

        log.debug("MacEFIGRUB.is_valid_stage1_device(%s) returning %s", device.name, valid)
        return valid


# Inherit abstract methods from BootLoader
# pylint: disable=abstract-method
class YabootBase(BootLoader):
    def write_config_password(self, config):
        if self.password:
            config.write("password=%s\n" % self.password)
            config.write("restricted\n")

    def write_config_images(self, config):
        for image in self.images:
            if not isinstance(image, LinuxBootLoaderImage):
                # mac os images are handled specially in the header on mac
                continue

            args = Arguments()
            if self.password:
                args.add("rd.shell=0")
            if image.initrd:
                initrd_line = "\tinitrd=%s/%s\n" % (self.boot_prefix,
                                                    image.initrd)
            else:
                initrd_line = ""

            root_device_spec = image.device.fstab_spec
            if root_device_spec.startswith("/"):
                root_line = "\troot=%s\n" % root_device_spec
            else:
                args.add("root=%s" % root_device_spec)
                root_line = ""

            args.update(self.boot_args)
            log.info("bootloader.py: used boot args: %s ", args)

            stanza = ("image=%(boot_prefix)s%(kernel)s\n"
                      "\tlabel=%(label)s\n"
                      "\tread-only\n"
                      "%(initrd_line)s"
                      "%(root_line)s"
                      "\tappend=\"%(args)s\"\n\n"
                      % {"kernel": image.kernel, "initrd_line": initrd_line,
                         "label": self.image_label(image),
                         "root_line": root_line, "args": args,
                         "boot_prefix": self.boot_prefix})
            config.write(stanza)


class Yaboot(YabootBase):
    name = "Yaboot"
    _config_file = "yaboot.conf"
    prog = "ybin"
    image_label_attr = "short_label"
    packages = ["yaboot"]

    # stage2 device requirements
    stage2_device_types = ["partition", "mdarray"]
    stage2_raid_levels = [raid.RAID1]

    #
    # configuration
    #

    @property
    def config_dir(self):
        conf_dir = "/etc"
        if self.stage2_device.format.mountpoint == "/boot":
            conf_dir = "/boot/etc"
        return conf_dir

    @property
    def config_file(self):
        return "%s/%s" % (self.config_dir, self._config_file)

    def write_config_header(self, config):
        if self.stage2_device.type == "mdarray":
            boot_part_num = self.stage2_device.parents[0].parted_partition.number
        else:
            boot_part_num = self.stage2_device.parted_partition.number

        # yaboot.conf timeout is in tenths of a second. Brilliant.
        header = ("# yaboot.conf generated by anaconda\n\n"
                  "boot=%(stage1dev)s\n"
                  "init-message=\"Welcome to %(product)s!\\nHit <TAB> for "
                  "boot options\"\n\n"
                  "partition=%(part_num)d\n"
                  "timeout=%(timeout)d\n"
                  "install=/usr/lib/yaboot/yaboot\n"
                  "delay=5\n"
                  "enablecdboot\n"
                  "enableofboot\n"
                  "enablenetboot\n"
                  % {"stage1dev": self.stage1_device.path,
                     "product": productName, "part_num": boot_part_num,
                     "timeout": self.timeout * 10})
        config.write(header)
        self.write_config_variant_header(config)
        self.write_config_password(config)
        config.write("\n")

    def write_config_variant_header(self, config):
        config.write("nonvram\n")
        config.write("mntpoint=/boot/yaboot\n")
        config.write("usemount\n")

    def write_config_post(self):
        super().write_config_post()

        # make symlink in /etc to yaboot.conf if config is in /boot/etc
        etc_yaboot_conf = util.getSysroot() + "/etc/yaboot.conf"
        if not os.access(etc_yaboot_conf, os.R_OK):
            try:
                os.symlink("../boot/etc/yaboot.conf", etc_yaboot_conf)
            except OSError as e:
                log.error("failed to create /etc/yaboot.conf symlink: %s", e)

    def write_config(self):
        if not os.path.isdir(util.getSysroot() + self.config_dir):
            os.mkdir(util.getSysroot() + self.config_dir)

        # this writes the config
        super().write_config()

    #
    # installation
    #

    def install(self, args=None):
        args = ["-f", "-C", self.config_file]
        rc = util.execInSysroot(self.prog, args)
        if rc:
            raise BootLoaderError("boot loader installation failed")


class IPSeriesGRUB2(GRUB2):

    # GRUB2 sets /boot bootable and not the PReP partition.  This causes the Open Firmware BIOS not
    # to present the disk as a bootable target.  If stage2_bootable is False, then the PReP partition
    # will be marked bootable. Confusing.
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

        buf = util.execWithCapture("nvram",
                                   ["--print-config=boot-device"])

        if len(buf) == 0:
            log.error("Failed to determine nvram boot device")
            return

        boot_list = buf.strip().replace("\"", "").split()
        log.debug("updateNVRAMBootList: boot_list = %s", boot_list)

        buf = util.execWithCapture("ofpathname",
                                   [self.stage1_device.path])

        if len(buf) > 0:
            boot_disk = buf.strip()
        else:
            log.error("Failed to translate boot path into device name")
            return

        # Place the disk containing the PReP partition first.
        # Remove all other occurances of it.
        boot_list = [boot_disk] + [x for x in boot_list if x != boot_disk]

        update_value = "boot-device=%s" % " ".join(boot_list)

        rc = util.execWithRedirect("nvram", ["--update-config", update_value])
        if rc:
            log.error("Failed to update new boot device order")

    #
    # In addition to the normal grub configuration variable, add one more to set the size of the
    # console's window to a standard 80x24
    #
    def write_defaults(self):
        super().write_defaults()

        defaults_file = "%s%s" % (util.getSysroot(), self.defaults_file)
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

class MacYaboot(Yaboot):
    prog = "mkofboot"
    can_dual_boot = True

    #
    # configuration
    #

    def write_config_variant_header(self, config):
        try:
            mac_os = [i for i in self.chain_images if i.label][0]
        except IndexError:
            pass
        else:
            config.write("macosx=%s\n" % mac_os.device.path)

        config.write("magicboot=/usr/lib/yaboot/ofboot\n")


class ZIPL(BootLoader):
    name = "ZIPL"
    config_file = "/etc/zipl.conf"
    packages = ["s390utils-base"]

    # stage2 device requirements
    stage2_device_types = ["partition"]

    @property
    def stage2_format_types(self):
        if productName.startswith("Red Hat "):          # pylint: disable=no-member
            return ["xfs", "ext4", "ext3", "ext2"]
        else:
            return ["ext4", "ext3", "ext2", "xfs"]

    image_label_attr = "short_label"
    preserve_args = ["cio_ignore", "rd.znet", "rd_ZNET", "zfcp.allow_lun_scan"]

    def __init__(self):
        super().__init__()
        self.stage1_name = None

    #
    # configuration
    #

    @property
    def boot_dir(self):
        return "/boot"

    def write_config_image(self, config, image, args):
        if image.initrd:
            initrd_line = "\tramdisk=%s/%s\n" % (self.boot_dir, image.initrd)
        else:
            initrd_line = ""

        stanza = ("[%(label)s]\n"
                  "\timage=%(boot_dir)s/%(kernel)s\n"
                  "%(initrd_line)s"
                  "\tparameters=\"%(args)s\"\n"
                  % {"label": self.image_label(image),
                     "kernel": image.kernel, "initrd_line": initrd_line,
                     "args": args,
                     "boot_dir": self.boot_dir})
        config.write(stanza)

    def update_bls_args(self, image, args):
        machine_id_path = util.getSysroot() + "/etc/machine-id"
        if not os.access(machine_id_path, os.R_OK):
            log.error("failed to read machine-id file")
            return

        with open(machine_id_path, "r") as fd:
            machine_id = fd.readline().strip()

        bls_dir = "%s%s/loader/entries/" % (util.getSysroot(), self.boot_dir)

        if image.kernel == "vmlinuz-0-rescue-" + machine_id:
            bls_path = "%s%s-0-rescue.conf" % (bls_dir, machine_id)
        else:
            bls_path = "%s%s-%s.conf" % (bls_dir, machine_id, image.version)

        if not os.access(bls_path, os.W_OK):
            log.error("failed to update boot args in BLS file %s", bls_path)
            return

        with open(bls_path, "r") as bls:
            lines = bls.readlines()
            for i, line in enumerate(lines):
                if line.startswith("options "):
                    lines[i] = "options %s\n" % (args)

        with open(bls_path, "w") as bls:
            bls.writelines(lines)

    def write_config_images(self, config):
        for image in self.images:
            if "kdump" in (image.initrd or image.kernel):
                # no need to create bootloader entries for kdump
                continue

            args = Arguments()
            args.add("root=%s" % image.device.fstab_spec)
            args.update(self.boot_args)
            if image.device.type == "btrfs subvolume":
                args.update(["rootflags=subvol=%s" % image.device.name])
            log.info("bootloader.py: used boot args: %s ", args)

            if self.use_bls:
                self.update_bls_args(image, args)
            else:
                self.write_config_image(config, image, args)

    def write_config_header(self, config):
        header = ("[defaultboot]\n"
                  "defaultauto\n"
                  "prompt=1\n"
                  "timeout={}\n"
                  "target=/boot\n")
        config.write(header.format(self.timeout))

        if self.use_bls and os.path.exists(util.getSysroot() + "/usr/sbin/new-kernel-pkg"):
            log.warning("BLS support disabled due new-kernel-pkg being present")
            self.use_bls = False

        if not self.use_bls:
            config.write("default={}\n".format(self.image_label(self.default)))

    #
    # installation
    #

    def install(self, args=None):
        buf = util.execWithCapture("zipl", [], root=util.getSysroot())
        for line in buf.splitlines():
            if line.startswith("Preparing boot device: "):
                # Output here may look like:
                #     Preparing boot device: dasdb (0200).
                #     Preparing boot device: dasdl.
                # We want to extract the device name and pass that.
                name = re.sub(r".+?: ", "", line)
                self.stage1_name = re.sub(r"(\s\(.+\))?\.$", "", name)
            # a limitation of s390x is that the kernel parameter list must not
            # exceed 896 bytes; there is nothing we can do about this, so just
            # catch the error and show it to the user instead of crashing
            elif line.startswith("Error: The length of the parameters "):
                errorHandler.cb(ZIPLError(line))

        if not self.stage1_name:
            raise BootLoaderError("could not find IPL device")

        # do the reipl
        util.reIPL(self.stage1_name)

class EXTLINUX(BootLoader):
    name = "EXTLINUX"
    _config_file = "extlinux.conf"
    _config_dir = "/boot/extlinux"

    stage2_format_types = ["ext4", "ext3", "ext2"]
    stage2_device_types = ["partition"]
    stage2_bootable = True

    # The extlinux bootloader doesn't have BLS support, the old grubby is needed
    packages = ["syslinux-extlinux", "grubby-deprecated"]

    @property
    def config_file(self):
        return "%s/%s" % (self._config_dir, self._config_file)

    @property
    def boot_prefix(self):
        """ Prefix, if any, to paths in /boot. """
        if self.stage2_device.format.mountpoint == "/":
            prefix = "/boot"
        else:
            prefix = ""

        return prefix

    def write_config_console(self, config):
        if not self.console:
            return

        console_arg = "console=%s" % self.console
        if self.console_options:
            console_arg += ",%s" % self.console_options
        self.boot_args.add(console_arg)

    def write_config_images(self, config):
        self.write_config_console(config)
        for image in self.images:
            args = Arguments()
            args.update(["root=%s" % image.device.fstab_spec, "ro"])
            if image.device.type == "btrfs subvolume":
                args.update(["rootflags=subvol=%s" % image.device.name])
            args.update(self.boot_args)
            log.info("bootloader.py: used boot args: %s ", args)

            # extlinux labels cannot have spaces
            label = "%s(%s)" % (self.image_label(image), image.version)
            label = label.replace(" ", "")
            stanza = ("label %(label)s\n"
                      "\tkernel %(boot_prefix)s/%(kernel)s\n"
                      "\tinitrd %(boot_prefix)s/%(initrd)s\n"
                      "\tappend %(args)s\n\n"
                      % {"label": label,
                         "kernel": image.kernel,
                         "initrd": image.initrd,
                         "args": args,
                         "boot_prefix": self.boot_prefix})
            config.write(stanza)

    def write_config_header(self, config):
        header = ("# extlinux.conf generated by anaconda\n\n"
                  "ui menu.c32\n\n"
                  "menu autoboot Welcome to %(productName)s. Automatic boot in # second{,s}. Press a key for options.\n"
                  "menu title %(productName)s Boot Options.\n"
                  "menu hidden\n\n"
                  "timeout %(timeout)d\n"
                  "#totaltimeout 9000\n\n"
                  % {"productName": productName, "timeout": self.timeout * 10})
        config.write(header)
        if self.default is not None:
            config.write("default %(default)s\n\n" % {"default": self.image_label(self.default).replace(" ", "")})
        self.write_config_password(config)

    def write_config_password(self, config):
        if self.password:
            config.write("menu master passwd %s\n" % self.password)
            config.write("menu notabmsg Press [Tab] and enter the password to edit options")

    def write_config_post(self):
        etc_extlinux = os.path.normpath(util.getSysroot() + "/etc/" + self._config_file)
        if not os.access(etc_extlinux, os.R_OK):
            try:
                os.symlink("../boot/%s" % self._config_file, etc_extlinux)
            except OSError as e:
                log.warning("failed to create /etc/extlinux.conf symlink: %s", e)

    #
    # installation
    #

    def install(self, args=None):
        args = ["--install", self._config_dir]
        rc = util.execInSysroot("extlinux", args)

        if rc:
            raise BootLoaderError("boot loader install failed")


# every platform that wants a bootloader needs to be in this dict
bootloader_by_platform = {
    platform.X86: GRUB2,
    platform.EFI: EFIGRUB,
    platform.MacEFI: MacEFIGRUB,
    platform.PPC: GRUB2,
    platform.IPSeriesPPC: IPSeriesGRUB2,
    platform.NewWorldPPC: MacYaboot,
    platform.S390: ZIPL,
    platform.Aarch64EFI: Aarch64EFIGRUB,
    platform.ARM: EXTLINUX,
    platform.ArmEFI: ArmEFIGRUB,
}

if flags.cmdline.get("legacygrub") == "1":
    log.info("Using legacy grub (0.9x)")
    bootloader_by_platform.update({
        platform.X86: GRUB,
        platform.EFI: EFIGRUB1,
    })

def get_bootloader():
    bootloader_proxy = STORAGE.get_proxy(BOOTLOADER)
    platform_name = platform.platform.__class__.__name__

    if bootloader_proxy.BootloaderType == BOOTLOADER_TYPE_EXTLINUX:
        cls = EXTLINUX
    else:
        cls = bootloader_by_platform.get(platform.platform.__class__, BootLoader)
    log.info("bootloader %s on %s platform", cls.__name__, platform_name)
    return cls()


# anaconda-specific functions

def writeSysconfigKernel(storage, version):
    # get the name of the default kernel package based on the version
    kernel_basename = "vmlinuz-" + version
    kernel_file = "/boot/%s" % kernel_basename
    if not os.path.isfile(util.getSysroot() + kernel_file):
        efi_dir = conf.bootloader.efi_dir
        kernel_file = "/boot/efi/EFI/%s/%s" % (efi_dir, kernel_basename)
        if not os.path.isfile(util.getSysroot() + kernel_file):
            log.error("failed to recreate path to default kernel image")
            return

    try:
        import rpm
    except ImportError:
        log.error("failed to import rpm python module")
        return

    ts = rpm.TransactionSet(util.getSysroot())
    mi = ts.dbMatch('basenames', kernel_file)
    try:
        h = next(mi)
    except StopIteration:
        log.error("failed to get package name for default kernel")
        return

    kernel = h.name.decode()

    f = open(util.getSysroot() + "/etc/sysconfig/kernel", "w+")
    f.write("# UPDATEDEFAULT specifies if new-kernel-pkg should make\n"
            "# new kernels the default\n")
    # only update the default if we're setting the default to linux (#156678)
    if storage.bootloader.default.device == storage.root_device:
        f.write("UPDATEDEFAULT=yes\n")
    else:
        f.write("UPDATEDEFAULT=no\n")
    f.write("\n")
    f.write("# DEFAULTKERNEL specifies the default kernel package type\n")
    f.write("DEFAULTKERNEL=%s\n" % kernel)
    if storage.bootloader.trusted_boot:
        f.write("# HYPERVISOR specifies the default multiboot kernel\n")
        f.write("HYPERVISOR=/boot/tboot.gz\n")
        f.write("HYPERVISOR_ARGS=logging=vga,serial,memory\n")
    f.close()

def writeBootLoaderFinal(storage, payload, ksdata):
    """ Do the final write of the bootloader. """

    # set up dracut/fips boot args
    # XXX FIXME: do this from elsewhere?
    storage.bootloader.set_boot_args(storage=storage,
                                     payload=payload)
    try:
        storage.bootloader.write()
    except BootLoaderError as e:
        log.error("bootloader.write failed: %s", e)
        if errorHandler.cb(e) == ERROR_RAISE:
            raise

def writeBootLoader(storage, payload, ksdata):
    """ Write bootloader configuration to disk.

        When we get here, the bootloader will already have a default linux
        image. We only have to add images for the non-default kernels and
        adjust the default to reflect whatever the default variant is.
    """
    if not storage.bootloader.skip_bootloader:
        stage1_device = storage.bootloader.stage1_device
        log.info("boot loader stage1 target device is %s", stage1_device.name)
        stage2_device = storage.bootloader.stage2_device
        log.info("boot loader stage2 target device is %s", stage2_device.name)

    storage.bootloader.menu_auto_hide = conf.bootloader.menu_auto_hide

    # Bridge storage EFI configuration to bootloader
    if hasattr(storage.bootloader, 'efi_dir'):
        storage.bootloader.efi_dir = conf.bootloader.efi_dir

    # Currently just rpmostreepayload shortcuts the rest of everything below
    if payload.handlesBootloaderConfiguration:
        if storage.bootloader.skip_bootloader:
            log.info("skipping boot loader install per user request")
            return
        writeBootLoaderFinal(storage, payload, ksdata)
        return

    # get a list of installed kernel packages
    # add whatever rescue kernels we can find to the end
    kernel_versions = list(payload.kernelVersionList)

    rescue_versions = glob(util.getSysroot() + "/boot/vmlinuz-*-rescue-*")
    rescue_versions += glob(
        util.getSysroot() + "/boot/efi/EFI/%s/vmlinuz-*-rescue-*" % conf.bootloader.efi_dir)
    kernel_versions += (f.split("/")[-1][8:] for f in rescue_versions)

    if not kernel_versions:
        log.warning("no kernel was installed -- boot loader config unchanged")
        return

    # all the linux images' labels are based on the default image's
    base_label = productName
    base_short_label = "linux"

    # The first one is the default kernel. Update the bootloader's default
    # entry to reflect the details of the default kernel.
    version = kernel_versions.pop(0)
    default_image = LinuxBootLoaderImage(device=storage.root_device,
                                         version=version,
                                         label=base_label,
                                         short=base_short_label)
    storage.bootloader.add_image(default_image)
    storage.bootloader.default = default_image

    # write out /etc/sysconfig/kernel
    writeSysconfigKernel(storage, version)

    if storage.bootloader.skip_bootloader:
        log.info("skipping boot loader install per user request")
        return

    # now add an image for each of the other kernels
    for version in kernel_versions:
        label = "%s-%s" % (base_label, version)
        short = "%s-%s" % (base_short_label, version)
        if storage.bootloader.trusted_boot:
            image = TbootLinuxBootLoaderImage(device=storage.root_device,
                                              version=version,
                                              label=label, short=short)
        else:
            image = LinuxBootLoaderImage(device=storage.root_device,
                                         version=version,
                                         label=label, short=short)
        storage.bootloader.add_image(image)

    writeBootLoaderFinal(storage, payload, ksdata)
