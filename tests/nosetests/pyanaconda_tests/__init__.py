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
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import gi
gi.require_version("GLib", "2.0")
from gi.repository import GLib

from textwrap import dedent
from unittest.mock import Mock, patch
from xml.etree import ElementTree

from pyanaconda.modules.common.constants.interfaces import KICKSTART_MODULE
from pyanaconda.modules.common.task import TaskInterface
from pyanaconda.dbus.xml import XMLGenerator


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


def compare_xml(test, first_xml, second_xml):
    """Compare two XML-formatted strings.

    Python 3.8 changed the order of the attributes and introduced
    the function canonicalize that should be used for testing.
    """
    # Prettify the XML.
    first_xml = XMLGenerator.prettify_xml(first_xml)
    second_xml = XMLGenerator.prettify_xml(second_xml)

    # Normalize the XML attributes.
    canonicalize = getattr(ElementTree, "canonicalize", lambda xml, *args, **kwargs: xml)
    first_xml = canonicalize(first_xml, with_comments=True)
    second_xml = canonicalize(second_xml, with_comments=True)

    test.assertEqual(first_xml, second_xml)


def check_kickstart_interface(test, interface, ks_in, ks_out=None, ks_valid=True, ks_tmp=None):
    """Test the parsing and generating of a kickstart module.

    :param test: instance of TestCase
    :param interface: instance of KickstartModuleInterface
    :param ks_in: string with the input kickstart
    :param ks_out: string with the output kickstart
    :param ks_valid: True if the input kickstart is valid, otherwise False
    :param ks_tmp: string with the temporary output kickstart
    """
    callback = Mock()
    interface.PropertiesChanged.connect(callback)

    # Read a kickstart,
    if ks_in is not None:
        ks_in = dedent(ks_in).strip()
        result = {k: v.unpack() for k, v in interface.ReadKickstart(ks_in).items()}

        if ks_valid:
            test.assertEqual(result, {"success": True})
        else:
            test.assertIn("success", result)
            test.assertEqual(result["success"], False)
            test.assertIn("line_number", result)
            test.assertIn("error_message", result)
            return

    if ks_out is None:
        return

    # Generate a kickstart
    ks_out = dedent(ks_out).strip()
    test.assertEqual(ks_out, interface.GenerateKickstart().strip())

    # Test the properties changed callback.
    if ks_in is not None:
        callback.assert_any_call(KICKSTART_MODULE.interface_name, {'Kickstarted': True}, [])
    else:
        test.assertEqual(interface.Kickstarted, False)
        callback.assert_not_called()

    if ks_tmp is None:
        ks_tmp = ks_out

    test.assertEqual(ks_tmp, interface.GenerateTemporaryKickstart().strip())


def check_dbus_property(test, interface_id, interface, property_name,
                        in_value, out_value=None, getter=None, setter=None, changed=None):
    """Check DBus property.

    :param test: instance of TestCase
    :param interface_id: instance of DBusInterfaceIdentifier
    :param interface: instance of a DBus interface
    :param property_name: a DBus property name
    :param in_value: an input value of the property
    :param out_value: an output value of the property or None
    :param getter: a property getter or None
    :param setter: a property setter or None
    :param changed: a dictionary of changed properties or None
    """
    callback = Mock()
    interface.PropertiesChanged.connect(callback)

    if out_value is None:
        out_value = in_value

    # Set the property.
    if not setter:
        setter = getattr(interface, "Set{}".format(property_name))

    setter(in_value)

    if not changed:
        changed = {property_name: out_value}

    callback.assert_called_once_with(interface_id.interface_name, changed, [])

    # Get the property.
    if not getter:
        getter = lambda: getattr(interface, property_name)

    test.assertEqual(getter(), out_value)


def check_task_creation(test, task_path, publisher, task_class):
    """Check that the DBus task is correctly created.

    :param test: instance of TestCase
    :param task_path: DBus path of the task
    :param publisher: Mock instance of the pyanaconda.dbus.DBus.publish_object
    :param task_class: class of the tested task
    """
    publisher.assert_called_once()
    object_path, obj = publisher.call_args[0]

    test.assertEqual(task_path, object_path)
    test.assertIsInstance(obj, TaskInterface)
    test.assertIsInstance(obj.implementation, task_class)

    return obj


def patch_dbus_publish_object(func):
    """Avoid publishing on dbus. Pass the mock inside the patched function.

    This is a shortcut to avoid constant patching with the path.

    # TODO: Extend this to patch the whole DBus object and pass in a useful abstraction.
    """
    return patch('pyanaconda.dbus.DBus.publish_object')


def patch_dbus_get_proxy(func):
    """Patch DBus proxies.

    This is a shortcut to avoid creating of DBus proxies using DBus.
    """
    return patch('pyanaconda.dbus.DBus.get_proxy')
