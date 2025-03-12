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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import os
from glob import glob

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.product import get_product_name
from pyanaconda.core.util import execWithRedirect
from pyanaconda.modules.common.errors.installation import BootloaderInstallationError
from pyanaconda.modules.storage.bootloader.image import LinuxBootLoaderImage

log = get_module_logger(__name__)

__all__ = ["configure_boot_loader", "create_rescue_images", "recreate_initrds"]


def create_rescue_images(sysroot, kernel_versions):
    """Create the rescue initrd images for each installed kernel."""
    # Always make sure the new system has a new machine-id, it
    # won't boot without it and some of the subsequent commands
    # like grub2-mkconfig and kernel-install will not work as well.
    log.info("Generating a new machine id.")

    if os.path.exists(sysroot + "/etc/machine-id"):
        os.unlink(sysroot + "/etc/machine-id")

    execWithRedirect(
        "systemd-machine-id-setup",
        [],
        root=sysroot
    )

    if os.path.exists(sysroot + "/usr/sbin/new-kernel-pkg"):
        use_nkp = True
    else:
        log.debug("new-kernel-pkg does not exist, calling scripts directly.")
        use_nkp = False

    for kernel in kernel_versions:
        log.info("Generating rescue image for %s.", kernel)

        if use_nkp:
            execWithRedirect(
                "new-kernel-pkg",
                ["--rpmposttrans", kernel],
                root=sysroot
            )
        else:
            files = glob(sysroot + "/etc/kernel/postinst.d/*")
            srlen = len(sysroot)
            files = sorted([
                f[srlen:] for f in files
                if os.access(f, os.X_OK)]
            )

            for file in files:
                execWithRedirect(
                    file,
                    [kernel, "/boot/vmlinuz-%s" % kernel],
                    root=sysroot
                )


def configure_boot_loader(sysroot, storage, kernel_versions):
    """Configure the boot loader.

    :param sysroot: a path to the root of the installed system
    :param storage: an instance of the storage
    :param kernel_versions: a list of kernel versions
    """
    log.debug("Configuring the boot loader.")

    # Get a list of installed kernel packages.
    # Add whatever rescue kernels we can find to the end.
    kernel_versions = kernel_versions + _get_rescue_kernel_versions(sysroot)

    if not kernel_versions:
        log.warning("No kernel was installed. The boot loader configuration unchanged.")
        return

    # Collect the boot loader images.
    _collect_os_images(storage, kernel_versions)

    # Write out /etc/sysconfig/kernel.
    _write_sysconfig_kernel(sysroot, storage)


def _get_rescue_kernel_versions(sysroot):
    """Get a list of rescue kernel versions.

    :param sysroot: a path to the root of the installed system
    :return: a list of rescue kernel versions
    """
    rescue_versions = glob(sysroot + "/boot/vmlinuz-*-rescue-*")
    rescue_versions += glob(sysroot + "/boot/efi/EFI/%s/vmlinuz-*-rescue-*" % conf.bootloader.efi_dir)
    return [f.split("/")[-1][8:] for f in rescue_versions]


def _collect_os_images(storage, kernel_versions):
    """Collect the OS images for the boot loader.

    :param storage: an instance of the storage
    :param kernel_versions: a list of kernel versions
    """
    log.debug("Collecting the OS images for: %s", ", ".join(kernel_versions))

    # all the linux images' labels are based on the default image's
    base_label = get_product_name()

    # The first one is the default kernel. Update the bootloader's default
    # entry to reflect the details of the default kernel.
    version = kernel_versions.pop(0)
    default_image = LinuxBootLoaderImage(
        device=storage.root_device,
        version=version,
        label=base_label
    )
    storage.bootloader.add_image(default_image)
    storage.bootloader.default = default_image

    # now add an image for each of the other kernels
    for version in kernel_versions:
        label = "%s-%s" % (base_label, version)
        image = LinuxBootLoaderImage(
            device=storage.root_device,
            version=version,
            label=label
        )
        storage.bootloader.add_image(image)


def _write_sysconfig_kernel(sysroot, storage):
    """Write to /etc/sysconfig/kernel.

    :param sysroot: a path to the root of the installed system
    :param storage: an instance of the storage
    """
    log.debug("Writing to /etc/sysconfig/kernel.")

    # get the name of the default kernel package based on the version
    kernel_basename = "vmlinuz-" + storage.bootloader.default.version
    kernel_file = "/boot/%s" % kernel_basename
    if not os.path.isfile(sysroot + kernel_file):
        efi_dir = conf.bootloader.efi_dir
        kernel_file = "/boot/efi/EFI/%s/%s" % (efi_dir, kernel_basename)
        if not os.path.isfile(sysroot + kernel_file):
            log.error("failed to recreate path to default kernel image")
            return

    try:
        import rpm
    except ImportError:
        log.error("failed to import rpm python module")
        return

    ts = rpm.TransactionSet(sysroot)
    mi = ts.dbMatch('basenames', kernel_file)
    try:
        h = next(mi)
    except StopIteration:
        log.error("failed to get package name for default kernel")
        return

    kernel = h.name

    f = open(sysroot + "/etc/sysconfig/kernel", "w+")
    f.write("# UPDATEDEFAULT specifies if kernel-install should make\n"
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


def create_bls_entries(sysroot, storage, kernel_versions):
    """Create BLS entries.

    :param sysroot: a path to the root of the installed system
    :param storage: an instance of the storage
    :param kernel_versions: a list of kernel versions
    """
    # Not using BLS configuration, skip it
    if os.path.exists(sysroot + "/usr/sbin/new-kernel-pkg"):
        return

    # Remove any existing BLS entries, they will not match the new system's
    # machine-id or /boot mountpoint.
    for file in glob(sysroot + "/boot/loader/entries/*.conf"):
        log.info("Removing old BLS entry: %s", file)
        os.unlink(file)

    # Create new BLS entries for this system
    for kernel in kernel_versions:
        log.info("Regenerating BLS info for %s", kernel)
        execWithRedirect(
            "kernel-install",
            ["add", kernel, "/lib/modules/{0}/vmlinuz".format(kernel)],
            root=sysroot
        )

    # Update the bootloader configuration to make sure that the BLS
    # entries will have the correct kernel cmdline and not the value
    # taken from /proc/cmdline, that is used to boot the live image.
    rc = execWithRedirect(
        "grub2-mkconfig",
        ["-o", "/etc/grub2.cfg"],
        root=sysroot
    )

    if rc:
        raise BootloaderInstallationError(
            "failed to write boot loader configuration"
        )


def recreate_initrds(sysroot, kernel_versions):
    """Recreate the initrds by calling new-kernel-pkg or dracut.

    This needs to be done after all configuration files have been
    written, since dracut depends on some of them.

    :param sysroot: a path to the root of the installed system
    :param kernel_versions: a list of kernel versions
    """
    if os.path.exists(sysroot + "/usr/sbin/new-kernel-pkg"):
        use_dracut = False
    else:
        log.debug("new-kernel-pkg does not exist, using dracut instead")
        use_dracut = True

    for kernel in kernel_versions:
        log.info("Recreating initrd for %s", kernel)

        if conf.target.is_image:
            # Dracut runs in the host-only mode by default, so we need to
            # turn it off by passing the -N option, because the mode is not
            # sensible for disk image installations. Using /dev/disk/by-uuid/
            # is necessary due to disk image naming.
            execWithRedirect(
                "dracut", [
                    "-N", "--persistent-policy", "by-uuid",
                    "-f", "/boot/initramfs-%s.img" % kernel, kernel
                ],
                root=sysroot
            )
        else:
            if use_dracut:
                execWithRedirect(
                    "depmod", ["-a", kernel], root=sysroot
                )
                execWithRedirect(
                    "dracut",
                    ["-f", "/boot/initramfs-%s.img" % kernel, kernel],
                    root=sysroot
                )
            else:
                execWithRedirect(
                    "new-kernel-pkg",
                    ["--mkinitrd", "--dracut", "--depmod", "--update", kernel],
                    root=sysroot
                )
