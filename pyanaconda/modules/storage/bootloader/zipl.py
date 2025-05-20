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
import re

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core import util
from pyanaconda.core.configuration.anaconda import conf
from pyanaconda.core.product import get_product_name
from pyanaconda.modules.storage.bootloader.base import (
    BootLoader,
    BootLoaderArguments,
    BootLoaderError,
)

log = get_module_logger(__name__)

__all__ = ["ZIPL"]


class ZIPL(BootLoader):
    """ZIPL."""

    name = "ZIPL"
    config_file = "/etc/zipl.conf"
    packages = ["s390utils-core"]

    # stage2 device requirements
    stage2_device_types = ["partition"]

    @property
    def stage2_format_types(self):
        if get_product_name().startswith("Red Hat "):  # pylint: disable=no-member
            return ["xfs", "ext4", "ext3", "ext2"]
        else:
            return ["ext4", "ext3", "ext2", "xfs"]

    image_label_attr = "short_label"

    def __init__(self):
        super().__init__()
        self.stage1_name = None
        self.secure = "auto"

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
        machine_id_path = conf.target.system_root + "/etc/machine-id"
        if not os.access(machine_id_path, os.R_OK):
            log.error("failed to read machine-id file")
            return

        with open(machine_id_path, "r") as fd:
            machine_id = fd.readline().strip()

        bls_dir = "%s%s/loader/entries/" % (conf.target.system_root, self.boot_dir)

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

            args = BootLoaderArguments()
            args.add("root=%s" % image.device.fstab_spec)
            args.update(self.boot_args)
            if image.device.type == "btrfs subvolume":
                args.add("rootflags=subvol=%s" % image.device.name)
            log.info("bootloader.py: used boot args: %s ", args)

            if self.use_bls:
                self.update_bls_args(image, args)
            else:
                self.write_config_image(config, image, args)

    def write_config_header(self, config):
        header = (
            "[defaultboot]\n"
            "defaultauto\n"
            "prompt=1\n"
            "timeout={}\n"
            "target=/boot\n"
            "secure={}\n"
        )
        config.write(header.format(
            self.timeout,
            self.secure
        ))

        if self.use_bls and os.path.exists(conf.target.system_root + "/usr/sbin/new-kernel-pkg"):
            log.warning("BLS support disabled due new-kernel-pkg being present")
            self.use_bls = False

        if not self.use_bls:
            config.write("default={}\n".format(self.image_label(self.default)))

    #
    # installation
    #

    def install(self, args=None):
        buf = util.execWithCapture("zipl", [], root=conf.target.system_root)
        for line in buf.splitlines():
            if line.startswith("Preparing boot device"):
                # Output here may look like:
                #     Preparing boot device: dasdb (0200).
                #     Preparing boot device: dasdl.
                # and since s390utils 2.25.0 as:
                #     Preparing boot device for LD-IPL: vda (0000).
                # We want to extract the device name and pass that.
                name = re.sub(r".+?: ", "", line)
                self.stage1_name = re.sub(r"(\s\(.+\))?\.$", "", name)
            # a limitation of s390x is that the kernel parameter list must not
            # exceed 896 bytes; there is nothing we can do about this, so just
            # catch the error and show it to the user instead of crashing
            elif line.startswith("Error: The length of the parameters "):
                raise BootLoaderError(line)

        if not self.stage1_name:
            raise BootLoaderError("could not find IPL device")

        # do the reipl
        util.reIPL(self.stage1_name)
