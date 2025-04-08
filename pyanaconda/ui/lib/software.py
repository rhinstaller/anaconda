#
# Copyright (C) 2023 Red Hat, Inc.
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
from collections import namedtuple
from blivet.arch import is_aarch64
from pyanaconda.core.i18n import _

FEATURE_UPSTREAM = "upstream"
FEATURE_64K = "64k"

KernelFeatures = namedtuple("KernelFeatures", ["upstream", "page_size_64k"])

def get_available_kernel_features(payload):
    """Returns a dictionary with that shows which kernels should be shown in the UI.
    """
    features = {
        FEATURE_UPSTREAM: any(payload.match_available_packages("kernel-redhat")),
        FEATURE_64K: is_aarch64() and any(payload.match_available_packages("kernel-64k"))
    }

    return features

def get_kernel_titles_and_descriptions():
    """Returns a dictionary with descriptions and titles for different kernel options.
    """
    kernel_features = {
        "standard": (_("kernel"), _("Optimized for stability")),
        "upstream": (_("kernel-redhat"), _("Access newer kernel features")),
        "4k": (_("4k"), _("More efficient memory usage in smaller environments")),
        "64k": (_("64k"), _("System performance gains for memory-intensive workloads")),
    }

    return kernel_features

def get_kernel_from_properties(features):
    """Translates the selection of required properties into a kernel package name and returns it
    or returns None if no properties were selected.
    """
    kernels = {
        # RedHat Kernel  ARM 64k    Package Name
        ( False,         False   ): None,
        ( True,          False   ): "kernel-redhat",
        ( False,         True    ): "kernel-64k",
        ( True,          True    ): "kernel-redhat-64k",
    }
    kernel_package = kernels[features]
    return kernel_package
