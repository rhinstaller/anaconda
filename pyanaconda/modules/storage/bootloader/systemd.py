#
# Copyright (C) 2022 Arm
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
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.constants import PAYLOAD_TYPE_DNF
from pyanaconda.core.i18n import _
from pyanaconda.core.path import join_paths
from pyanaconda.core.product import get_product_name
from pyanaconda.modules.common.constants.services import PAYLOADS
from pyanaconda.modules.storage.bootloader.base import BootLoader, BootLoaderError

log = get_module_logger(__name__)

__all__ = ["SystemdBoot"]

class SystemdBoot(BootLoader):
    """Systemd-boot.

    Systemd-boot is dead simple, it basically provides a second boot menu
    and injects the kernel parms into an efi stubbed kernel, which in turn
    (optionally) loads it's initrd. As such there aren't any filesystem or
    drivers to worry about as everything needed is provided by UEFI. Even the
    console remains on the UEFI framebuffer, or serial as selected by UEFI.
    Basically rather than trying to be another mini-os (like grub) and duplicate
    much of what UEFI provides, it simply utilizes the existing services.

    Further, while we could keep stage1 (ESP) and stage2 (/boot) seperate it
    simplifies things just to merge them and place the kernel/initrd on the
    ESP. This requires a larger than normal ESP, but for now we assume that
    this linux installer is creating the partitions, so where the space
    is allocated doesn't matter.

    """
    name = "SDBOOT"
    # oddly systemd-boot files are part of the systemd-udev package
    # and in /usr/lib/systemd/boot/efi/systemd-boot[aa64].efi
    # and the systemd stubs are in /usr/lib/systemd/linuxaa64.efi.stub
    _config_file = "loader.conf"
    _config_dir = "/loader"

    # systemd-boot doesn't require a stage2 as
    # everything is stored on the ESP
    stage2_max_end = None
    stage2_is_valid_stage1 = True
    stage2_required = False

    #
    # configuration
    #

    @property
    def config_dir(self):
        """ Full path to configuration directory. """
        esp = util.execWithCapture("bootctl", [ "--print-esp-path" ],
                                   root=conf.target.system_root)
        return esp.strip() + self._config_dir

    @property
    def config_file(self):
        """ Full path to configuration file. """
        return "%s/%s" % (self.config_dir, self._config_file)

    def check(self):
        """Verify the bootloader configuration."""
        if self._get_payload_type() != PAYLOAD_TYPE_DNF:
            self.errors.append(_(
                "Systemd-boot cannot be utilized with the current type of payload. "
                "Choose an installation media that supports package installation."
            ))
            return False

        return super().check()

    @staticmethod
    def _get_payload_type():
        """Get the type of the active payload."""
        payloads_proxy = PAYLOADS.get_proxy()
        object_path = payloads_proxy.ActivePayload

        if not object_path:
            return None

        object_proxy = PAYLOADS.get_proxy(object_path)
        return object_proxy.Type

    def write_config(self):
        log.info("systemd.py: write_config systemd start")

        # Rewrite the loader.conf
        # For now we are just updating the timeout to actually
        # implement the bootloader --timeout option
        config_path = join_paths(conf.target.system_root, self.config_file)
        log.info("systemd.py: write_config systemd loader conf : %s ", config_path)

        with open(config_path, "w") as config:
            config.write("timeout "+ str(self.timeout) + "\n")
            config.write("#console-mode keep\n")

        # update /etc/kernel/cmdline
        # should look something like "root=UUID=45b931b7-592a-46dc-9c33-d38d5901ec29 ro resume=/dev/sda3"
        config_path = join_paths(conf.target.system_root, "/etc/kernel/cmdline")
        log.info("systemd.py: write_config systemd commandline : %s ", config_path)
        with open(config_path, "w") as config:
            args = str(self.boot_args)
            log.info("systemd.py: systemd used boot args: %s ", args)

            # pick up the UUID of the mounted rootfs,
            root_uuid = util.execWithCapture("findmnt", [ "-sfn", "-oUUID", "/" ],
                                             root=conf.target.system_root)
            args += " root=UUID=" + root_uuid

            for image in self.images:
                if image.device.type == "btrfs subvolume":
                    args += "rootflags=subvol=" + image.device.name

            config.write(args)

        # rather than creating a mess in python lets just
        # write the options above, and run a script which will merge the
        # boot cmdline (after stripping inst. and BOOT_) with the anaconda
        # settings and the kernel-install recovery/etc options.
        rc = util.execWithRedirect(
            "/usr/sbin/updateloaderentries",
            [" "],
            root=conf.target.system_root
        )
        if rc:
            raise BootLoaderError(_("Failed to write boot loader configuration. "
                                    "More information may be found in the log files stored in /tmp"))

    #
    # installation
    #
    def install(self, args=None):
        log.info("systemd.py: install systemd boot install (root=%s)", conf.target.system_root)

        # the --esp-path= isn't strictly required, but we want to be explicit about it.
        rc = util.execWithRedirect(
            "bootctl",
            [
                "install",
                "--esp-path=/boot/efi",
                "--efi-boot-option-description=" + get_product_name().split("-")[0]
            ],
            root=conf.target.system_root,
            env_prune=['MALLOC_PERTURB_']
        )
        if rc:
            raise BootLoaderError(_("bootctl failed to install UEFI boot loader. "
                                    "More information may be found in the log files stored in /tmp"))

    def write_config_images(self, config):
        return True
