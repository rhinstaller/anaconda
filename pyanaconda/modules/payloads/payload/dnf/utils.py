#
# Copyright (C) 2020 Red Hat, Inc.
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
import dnf.subject

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.regexes import VERSION_DIGITS
from pyanaconda.core.util import is_lpae_available
from pyanaconda.product import productName, productVersion

log = get_module_logger(__name__)


def get_kernel_package(dnf_base, exclude_list):
    """Get an installable kernel package.

    :param dnf_base: a DNF base
    :param exclude_list: a list of excluded packages
    :return: a package name or None
    """
    if "kernel" in exclude_list:
        return None

    # Get the kernel packages.
    kernels = ["kernel"]

    # ARM systems use either the standard Multiplatform or LPAE platform.
    if is_lpae_available():
        kernels.insert(0, "kernel-lpae")

    # Find an installable one.
    for kernel_package in kernels:
        subject = dnf.subject.Subject(kernel_package)
        installable = bool(subject.get_best_query(dnf_base.sack))

        if installable:
            log.info("kernel: selected %s", kernel_package)
            return kernel_package

        log.info("kernel: no such package %s", kernel_package)

    log.error("kernel: failed to select a kernel from %s", kernels)
    return None


def get_product_release_version():
    """Get a release version of the product.

    :return: a string with the release version
    """
    try:
        release_version = VERSION_DIGITS.match(productVersion).group(1)
    except AttributeError:
        release_version = "rawhide"

    log.debug("Release version of %s is %s.", productName, release_version)
    return release_version
