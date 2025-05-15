#
# Snapshot device
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
from blivet.devices import LVMLogicalVolumeDevice
from pykickstart.errors import KickstartParseError

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.i18n import _

log = get_module_logger(__name__)

__all__ = ["get_snapshot_device"]


def get_snapshot_device(request, devicetree):
    """Get the ThinLV snapshot device.

    :param request: a snapshot request
    :param devicetree: a device tree to look up devices
    :return: a model of the ThinLV snapshot
    """
    snap_name = request.name.replace('-', '--')
    origin = request.origin.replace('-', '--').replace('/', '-')
    origin_dev = devicetree.get_device_by_name(origin)
    log.debug("Snapshot: name %s has origin %s", request.name, origin_dev)

    if origin_dev is None:
        raise KickstartParseError(_("Snapshot: origin \"%s\" doesn't exist!")
                                  % request.origin, lineno=request.lineno)

    if not origin_dev.is_thin_lv:
        raise KickstartParseError(_("Snapshot: origin \"%(origin)s\" of snapshot "
                                    "\"%(name)s\" is not a valid thin LV device.")
                                  % {"origin": request.origin, "name": request.name},
                                  lineno=request.lineno)

    if devicetree.get_device_by_name("%s-%s" % (origin_dev.vg.name, snap_name)):
        raise KickstartParseError(_("Snapshot %s already exists.") % request.name,
                                  lineno=request.lineno)
    try:
        return LVMLogicalVolumeDevice(
            name=request.name,
            parents=[origin_dev.pool],
            seg_type="thin",
            origin=origin_dev
        )
    except ValueError as e:
        raise KickstartParseError(str(e), lineno=request.lineno) from e
