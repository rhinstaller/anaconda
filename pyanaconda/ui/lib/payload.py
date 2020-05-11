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
from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import PAYLOAD_TYPE_DNF
from pyanaconda.modules.common.constants.services import PAYLOADS

log = get_module_logger(__name__)


def create_payload(payload_type=PAYLOAD_TYPE_DNF, activate=True):
    """Create a payload module.

    :param payload_type: a payload type
    :param activate: True to activate the payload, otherwise False
    :return: a proxy of a payload module
    """
    payloads_proxy = PAYLOADS.get_proxy()
    object_path = payloads_proxy.CreatePayload(payload_type)

    if activate:
        payloads_proxy.ActivatePayload(object_path)

    return PAYLOADS.get_proxy(object_path)


def get_payload(payload_type=PAYLOAD_TYPE_DNF):
    """Get a payload of the specified type.

    If there is no active payload of the specified type,
    we will create and activate a new payload.

    :return: a proxy of a payload module
    """
    payloads_proxy = PAYLOADS.get_proxy()
    object_path = payloads_proxy.ActivePayload

    # Choose the active payload.
    if object_path:
        object_proxy = PAYLOADS.get_proxy(object_path)

        # Check the type of the active payload.
        if object_proxy.Type == payload_type:
            return object_proxy

    # Or create a new payload.
    return create_payload(payload_type)
