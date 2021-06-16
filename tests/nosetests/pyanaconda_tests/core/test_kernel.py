#
# Copyright (C) 2019  Red Hat, Inc.
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

import unittest
from pyanaconda.core.kernel import KernelArguments, kernel_arguments
import collections


class KernelArgumentsTests(unittest.TestCase):

    def value_retrieval_test(self):
        """KernelArguments value retrieval test."""

        ka = KernelArguments.from_string(
            "inst.blah foo=anything inst.bar=1 baz=0 nowhere inst.nothing=indeed beep=off "
            "derp=no nobody=0")

        # test using "in" operator on the class
        self.assertTrue("blah" in ka)
        self.assertTrue("foo" in ka)
        self.assertFalse("thisisnotthere" in ka)
        self.assertFalse("body" in ka)
        self.assertTrue("nobody" in ka)

        # test the get() method
        self.assertEqual(ka.get("foo"), "anything")
        self.assertIsNone(ka.get("thisisnotthere"))
        self.assertEqual(ka.get("thisisnotthere", "fallback"), "fallback")

        # test the is_enabled() method
        self.assertTrue(ka.is_enabled("blah"))  # present
        self.assertTrue(ka.is_enabled("foo"))  # any value
        self.assertTrue(ka.is_enabled("bar"))  # 1 = any value
        self.assertFalse(ka.is_enabled("baz"))  # 0
        self.assertTrue(ka.is_enabled("nowhere"))  # present
        self.assertTrue(ka.is_enabled("nothing"))  # present
        self.assertFalse(ka.is_enabled("beep"))  # off
        self.assertTrue(ka.is_enabled("derp"))  # no = any value
        self.assertFalse(ka.is_enabled("nobody"))  # 0
        self.assertFalse(ka.is_enabled("thing"))  # not present
        self.assertFalse(ka.is_enabled("where"))  # not present

    def real_parsing_and_adding_test(self):
        """Test file spec handling in KernelArguments."""

        ka = KernelArguments()
        self.assertEqual(ka.read(["/proc/cmdlin*", "/nonexistent/file"]), ["/proc/cmdline"])
        self.assertEqual(ka.read("/another/futile/attempt"), [])

    def special_argument_handling_test(self):
        """Test handling of special arguments in KernelArguments."""

        ka = KernelArguments.from_string("modprobe.blacklist=floppy modprobe.blacklist=reiserfs")
        self.assertEqual(ka.get("modprobe.blacklist"), "floppy reiserfs")
        ka.read_string("inst.addrepo=yum inst.addrepo=dnf")
        self.assertEqual(ka.get("addrepo"), ["yum", "dnf"])
        ka.read_string("inst.ks=kickstart")
        self.assertEqual(ka.get("ks"), "kickstart")

    def items_test(self):
        """Test KernelArguments access to contents with iterator."""

        ka = KernelArguments.from_defaults()
        it = ka.items()
        self.assertIsInstance(it, collections.Iterable)
        root_seen = False
        for k, v in it:  # pylint: disable=unused-variable
            if k == "root":
                root_seen = True
        self.assertTrue(root_seen)

    def items_raw_test(self):
        """Test KernelArguments access to raw contents with iterator."""

        ka = KernelArguments.from_string(
            "blah inst.foo=anything inst.nothing=indeed")
        it = ka.items_raw()

        self.assertIsInstance(it, collections.Iterable)

        res = dict()
        for k, v in it:
            res[k] = v

        self.assertIn("inst.foo", res)
        self.assertIn("blah", res)
        self.assertIn("inst.nothing", res)

        self.assertEqual(res["inst.nothing"], "indeed")

    def shared_instance_test(self):
        """Test the kernel.kernel_arguments instance."""
        self.assertTrue("root" in kernel_arguments)
