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
from glob import glob

from pyanaconda.bootloader.base import BootLoaderError
from pyanaconda.bootloader.image import LinuxBootLoaderImage
from pyanaconda.core import util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.errors import errorHandler, ERROR_RAISE
from pyanaconda.product import productName

from pyanaconda.anaconda_loggers import get_module_logger
log = get_module_logger(__name__)

__all__ = ["write_boot_loader"]


def write_boot_loader(storage, payload):
    """ Write bootloader configuration to disk.

        When we get here, the bootloader will already have a default linux
        image. We only have to add images for the non-default kernels and
        adjust the default to reflect whatever the default variant is.
    """
    # Set up the boot loader.
    storage.bootloader.menu_auto_hide = conf.bootloader.menu_auto_hide

    # Bridge storage EFI configuration to bootloader
    if hasattr(storage.bootloader, 'efi_dir'):
        storage.bootloader.efi_dir = conf.bootloader.efi_dir

    # Configure the boot loader.
    if not payload.handlesBootloaderConfiguration:
        _configure_boot_loader(storage, payload.kernelVersionList)

    # Should we skip the installation?
    if storage.bootloader.skip_bootloader:
        log.info("skipping boot loader install per user request")
        return

    # Install the bootloader.
    _set_boot_arguments(storage)
    _install_boot_loader(storage)


def _configure_boot_loader(storage, kernel_versions):
    """Configure the bootloader."""
    log.debug("Configuring the boot loader.")

    # get a list of installed kernel packages
    # add whatever rescue kernels we can find to the end
    kernel_versions = list(kernel_versions)

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
    _write_sysconfig_kernel(storage, version)

    # now add an image for each of the other kernels
    for version in kernel_versions:
        label = "%s-%s" % (base_label, version)
        short = "%s-%s" % (base_short_label, version)
        image = LinuxBootLoaderImage(device=storage.root_device,
                                     version=version,
                                     label=label, short=short)
        storage.bootloader.add_image(image)


def _write_sysconfig_kernel(storage, version):
    """Write to /etc/sysconfig/kernel."""
    log.debug("Writing to /etc/sysconfig/kernel.")

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
    f.close()


def _set_boot_arguments(storage):
    """Set up the final boot arguments."""
    # FIXME: do this from elsewhere?
    storage.bootloader.set_boot_args(storage)


def _install_boot_loader(storage):
    """Do the final write of the boot loader."""
    log.debug("Installing the boot loader.")

    stage1_device = storage.bootloader.stage1_device
    log.info("boot loader stage1 target device is %s", stage1_device.name)

    stage2_device = storage.bootloader.stage2_device
    log.info("boot loader stage2 target device is %s", stage2_device.name)

    try:
        storage.bootloader.write()
    except BootLoaderError as e:
        log.error("bootloader.write failed: %s", e)
        if errorHandler.cb(e) == ERROR_RAISE:
            raise
