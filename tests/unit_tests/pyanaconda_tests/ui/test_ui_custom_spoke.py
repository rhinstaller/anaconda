#
# Copyright (C) 2020  Red Hat, Inc.
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
import copy
import unittest
from textwrap import dedent

from blivet.size import Size

from pyanaconda.core.storage import DEVICE_TYPES
from pyanaconda.modules.common.structures.device_factory import DeviceFactoryRequest
from pyanaconda.ui.gui.spokes.lib.custom_storage_helpers import (
    generate_request_description,
)


class CustomStorageHelpersTestCase(unittest.TestCase):
    """Test the functions and classes of the custom spoke."""

    def test_generate_request_description(self):
        """Test generate_request_description."""
        request = DeviceFactoryRequest()
        request.device_spec = "dev3"
        request.disks = ["dev1", "dev2"]
        request.device_name = "dev3"
        request.device_type = DEVICE_TYPES.LVM_THINP
        request.device_size = Size("10 GiB").get_bytes()
        request.mount_point = "/"
        request.format_type = "xfs"
        request.label = "root"
        request.device_encrypted = True
        request.luks_version = "luks1"
        request.device_raid_level = "raid1"

        expected = dedent("""
        {
        container-encrypted = False
        container-name = ''
        container-raid-level = ''
        container-size-policy = 0
        container-spec = ''
        device-encrypted = True
        device-name = 'dev3'
        device-raid-level = 'raid1'
        device-size = 10737418240
        device-spec = 'dev3'
        device-type = <DEVICE_TYPES.LVM_THINP: 5>
        disks = ['dev1', 'dev2']
        format-type = 'xfs'
        label = 'root'
        luks-version = 'luks1'
        mount-point = '/'
        reformat = False
        }
        """).strip()

        assert generate_request_description(request) == expected

        original = copy.deepcopy(request)
        assert generate_request_description(request, original) == expected

        request.device_name = "dev4"
        request.disks = ["dev1"]
        request.device_encrypted = False

        expected = dedent("""
        {
        container-encrypted = False
        container-name = ''
        container-raid-level = ''
        container-size-policy = 0
        container-spec = ''
        device-encrypted = True -> False
        device-name = 'dev3' -> 'dev4'
        device-raid-level = 'raid1'
        device-size = 10737418240
        device-spec = 'dev3'
        device-type = <DEVICE_TYPES.LVM_THINP: 5>
        disks = ['dev1', 'dev2'] -> ['dev1']
        format-type = 'xfs'
        label = 'root'
        luks-version = 'luks1'
        mount-point = '/'
        reformat = False
        }
        """).strip()

        assert generate_request_description(request, original) == expected
