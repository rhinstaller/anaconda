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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
from blivet.size import Size
from dasbus.client.proxy import get_object_path

from pyanaconda.anaconda_loggers import get_module_logger
from pyanaconda.core.constants import PAYLOAD_TYPE_DNF
from pyanaconda.modules.common.constants.objects import DEVICE_TREE
from pyanaconda.modules.common.constants.services import PAYLOADS, STORAGE
from pyanaconda.modules.common.structures.storage import DeviceData, DeviceFormatData
from pyanaconda.modules.common.task import sync_run_task

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


def create_source(source_type):
    """Create a source.

    :param source_type: a source type
    :return: a DBus proxy of a source
    """
    payloads_proxy = PAYLOADS.get_proxy()
    object_path = payloads_proxy.CreateSource(source_type)
    return PAYLOADS.get_proxy(object_path)


def set_source(payload_proxy, source_proxy):
    """Attach the source to the payload.

    :param payload_proxy: a DBus proxy of a payload
    :param source_proxy: a DBus proxy of a source
    """
    object_path = get_object_path(source_proxy)
    payload_proxy.Sources = [object_path]


def get_source(payload_proxy):
    """Get a source of the given payload.

    If the payload has one or more sources, return the first one.

    If the payload has no sources and the default source type
    is specified, create a default source.

    If the payload has no sources and the default source type
    is not specified, raise an exception.

    :param payload_proxy: a DBus proxy of a payload
    :return: a DBus proxy of a source
    :raise: ValueError if there is no source to return
    """
    sources = payload_proxy.Sources

    if sources:
        # Return the first source in the list. We don't
        # really support multiple sources at this moment.
        return PAYLOADS.get_proxy(sources[0])

    # Or create a new source of the specified type
    # and attach it to the given payload.
    source = create_source(payload_proxy.DefaultSourceType)
    set_source(payload_proxy, source)

    return source


def set_up_sources(payload_proxy):
    """Set up the sources of the given payload.

    :param payload_proxy: a DBus proxy of a payload
    """
    task_path = payload_proxy.SetUpSourcesWithTask()
    task_proxy = PAYLOADS.get_proxy(task_path)
    sync_run_task(task_proxy)


def tear_down_sources(payload_proxy):
    """Tear down the sources of the given payload.

    :param payload_proxy: a DBus proxy of a payload
    """
    task_path = payload_proxy.TearDownSourcesWithTask()
    task_proxy = PAYLOADS.get_proxy(task_path)
    sync_run_task(task_proxy)


def find_potential_hdiso_sources():
    """Find potential HDISO sources.

    Return a generator yielding Device instances that may have HDISO install
    media somewhere. Candidate devices are simply any that we can mount.

    :return: a list of device IDs
    """
    device_tree = STORAGE.get_proxy(DEVICE_TREE)
    return device_tree.FindMountablePartitions()


def get_hdiso_source_info(device_tree, device_id):
    """Get info about a potential HDISO source.

    :param device_tree: a proxy of a device tree
    :param device_id: a device ID
    :return: a dictionary with a device info
    """
    device_data = DeviceData.from_structure(
        device_tree.GetDeviceData(device_id)
    )

    format_data = DeviceFormatData.from_structure(
        device_tree.GetFormatData(device_id)
    )

    disk_data = DeviceData.from_structure(
        device_tree.GetDeviceData(device_data.parents[0])
    )

    return {
        "model": disk_data.attrs.get("model", "").replace("_", " "),
        "path": device_data.path,
        "size": Size(device_data.size),
        "format": format_data.description,
        "label": format_data.attrs.get("label") or format_data.attrs.get("uuid") or ""
    }


def get_hdiso_source_description(device_info):
    """Get a description of a potential HDISO source.

    :param device_info: a dictionary with a device info
    :return: a string with a device description
    """
    return "{model} {path} ({size}) {format} {label}".format(**device_info)
