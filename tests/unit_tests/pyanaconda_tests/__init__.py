#
# Copyright (C) 2017  Red Hat, Inc.
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
from collections import defaultdict

import re

import gi
gi.require_version("GLib", "2.0")
from gi.repository import GLib

from contextlib import ContextDecorator
from textwrap import dedent
from unittest.mock import Mock, patch

from dasbus.server.template import BasicInterfaceTemplate
from pyanaconda.modules.common.constants.interfaces import KICKSTART_MODULE
from pyanaconda.modules.common.structures.kickstart import KickstartReport
from pyanaconda.modules.common.task import TaskInterface
from dasbus.typing import get_native


class run_in_glib(object):
    """Run the test methods in GLib.

    :param timeout: Timeout in seconds when the loop will be killed.
    """

    def __init__(self, timeout):
        self._timeout = timeout
        self._result = None

    def __call__(self, func):

        def kill_loop(loop):
            loop.quit()
            return False

        def run_in_loop(*args, **kwargs):
            self._result = func(*args, **kwargs)

        def create_loop(*args, **kwargs):
            loop = GLib.MainLoop()

            GLib.idle_add(run_in_loop, *args, **kwargs)
            GLib.timeout_add_seconds(self._timeout, kill_loop, loop)

            loop.run()

            return self._result

        return create_loop


def clear_version_from_kickstart_string(ks_in):
    """Remove leading line comment with version from kickstart, if present.

    :param str ks_in: string with input kickstart
    :return str: string with output kickstart
    """

    return re.sub(
        r"# Generated [^\n]+\n",
        "",
        ks_in
    )


def check_kickstart_interface(interface, ks_in, ks_out=None, ks_valid=True, ks_tmp=None):
    """Test the parsing and generating of a kickstart module.

    :param interface: instance of KickstartModuleInterface
    :param ks_in: string with the input kickstart
    :param ks_out: string with the output kickstart
    :param ks_valid: True if the input kickstart is valid, otherwise False
    :param ks_tmp: string with the temporary output kickstart
    """
    callback = PropertiesChangedCallback()
    interface.PropertiesChanged.connect(callback)

    result = None

    # Read a kickstart,
    if ks_in is not None:
        ks_in = dedent(ks_in).strip()
        result = KickstartReport.from_structure(
            interface.ReadKickstart(ks_in)
        )
        assert ks_valid == result.is_valid()

    if not ks_valid:
        return result

    if ks_out is None:
        return result

    # Generate a kickstart
    ks_out = dedent(ks_out).strip()
    ks_generated = clear_version_from_kickstart_string(interface.GenerateKickstart()).strip()
    assert ks_out == ks_generated

    # Test the properties changed callback.
    if ks_in is not None:
        callback.assert_any_call(KICKSTART_MODULE.interface_name, {'Kickstarted': True}, [])
    else:
        assert interface.Kickstarted is False
        callback.assert_not_called()

    # Test the temporary kickstart.
    if ks_tmp is None:
        return

    ks_tmp = dedent(ks_tmp).strip()
    assert ks_tmp == interface.GenerateTemporaryKickstart().strip()

    return result


class PropertiesChangedCallback(Mock):
    """Mocked callback for the DBus signal PropertiesChanged.

    The arguments of the call are unpacked into native values.
    """
    def __call__(self, interface, changed, invalid):  # pylint: disable=arguments-differ
        return super().__call__(
            interface, {k: v.unpack() for k, v in changed.items()}, invalid
        )


def check_dbus_property(interface_id, interface, property_name,
                        in_value, out_value=None, getter=None, setter=None, changed=None):
    """Check DBus property.

    :param interface_id: instance of DBusInterfaceIdentifier
    :param interface: instance of a DBus interface
    :param property_name: a DBus property name
    :param in_value: an input value of the property
    :param out_value: an output value of the property or None
    :param getter: a property getter or None
    :param setter: a property setter or None
    :param changed: a dictionary of changed properties or None
    """
    callback = PropertiesChangedCallback()
    interface.PropertiesChanged.connect(callback)

    if out_value is None:
        out_value = in_value

    # Set the property.
    if not setter:
        setter = getattr(interface, "Set{}".format(property_name))

    setter(in_value)

    if not changed:
        changed = {property_name: out_value}

    callback.assert_called_once_with(interface_id.interface_name, get_native(changed), [])

    # Get the property.
    if not getter:
        getter = lambda: getattr(interface, property_name)

    assert getter() == out_value


def check_task_creation(task_path, publisher, task_class, index=0):
    """Check that the DBus task is correctly created.

    :param task_path: DBus path of the task
    :param publisher: Mock instance of the publish_object method
    :param task_class: class of the tested task
    :param index: an index of the published object
    :return: instance of the task
    """
    obj = check_dbus_object_creation(task_path, publisher, task_class, index)
    assert isinstance(obj, TaskInterface)
    return obj


def check_task_creation_list(task_paths, publisher, task_classes):
    """Check that the list of DBus task is correctly created.

    :param task_paths: DBus paths of the tasks
    :type task_paths: [str]
    :param publisher: Mock instance of the publish_object method
    :param task_classes: list of classes of the tested tasks; the order is important here

    :return: list of instances of tasks
    """
    task_proxies = []
    task_count = len(task_paths)

    # Check the number of published tasks.
    assert task_count == publisher.call_count
    assert task_count == len(task_classes)

    # Check each published task.
    for i in range(task_count):
        task_proxy = check_task_creation(task_paths[i], publisher, task_classes[i], i)
        task_proxies.append(task_proxy)

    return task_proxies


def check_dbus_object_creation(path, publisher, klass, index=0):
    """Check that the custom DBus object is correctly created.

    :param path: DBus path of the published object
    :param publisher: Mock instance of the publish_object method
    :param klass: class of the tested DBus object
    :param index: an index of the published object
    """
    # A valid index of a call should be less than the number of calls.
    assert index < publisher.call_count
    object_path, obj = publisher.call_args_list[index][0]

    assert path == object_path
    assert isinstance(obj.implementation, klass)
    assert isinstance(obj, BasicInterfaceTemplate)
    return obj


def patch_dbus_publish_object(func):
    """Avoid publishing on dbus. Pass the mock inside the patched function.

    This is a shortcut to avoid constant patching with the path.

    # TODO: Extend this to patch the whole DBus object and pass in a useful abstraction.
    """
    return patch('pyanaconda.core.dbus.DBus.publish_object')(func)


def patch_dbus_get_proxy(func):
    """Patch DBus proxies.

    This is a shortcut to avoid creating of DBus proxies using DBus.
    """
    return patch('pyanaconda.core.dbus.DBus.get_proxy')(func)


def patch_system_dbus_get_proxy(func):
    """Patch DBus proxies on the system message bus.

    This is a shortcut to avoid creating of DBus proxies using DBus.
    """
    return patch('pyanaconda.core.dbus.SystemBus.get_proxy')(func)


def patch_dbus_get_proxy_with_cache(func):
    """Patch DBus proxies with a cache.

    This decorator will patch the get_proxy method of the DBus class.
    The patched method will create and return an instance of Mock for
    the given service name and object path and keep it in a cache for
    next use. It will return the same instance of Mock for the same
    arguments.

    It means that you can use DBus identifiers to set up the state of
    DBus modules or to check the current state. It is useful for testing
    functions that manipulate with multiple DBus objects.

    For example:

        network = NETWORK.get_proxy()
        network.Connected.return_value = True

        bootloader = STORAGE.get_proxy(BOOTLOADER)
        bootloader.IsPasswordSet = False

    """
    proxies = defaultdict(Mock)

    def mock_get(service_name, object_path, *args, **kwargs):
        return proxies[(service_name, object_path)]

    return patch('pyanaconda.core.dbus.DBus.get_proxy', side_effect=mock_get)(func)


class reset_boot_loader_factory(ContextDecorator):
    """Reset the boot loader factory.

    Use this decorator to reset the boot loader factory
    for the unit tests that could modify it.
    """
    def __init__(self, default_type=None):
        self._default_type = default_type

    def __enter__(self):
        from pyanaconda.modules.storage.bootloader import BootLoaderFactory
        BootLoaderFactory.set_default_class(self._default_type)
        return self

    def __exit__(self, *exc):
        from pyanaconda.modules.storage.bootloader import BootLoaderFactory
        BootLoaderFactory.set_default_class(None)
        return False
