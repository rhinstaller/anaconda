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
            "blah foo=anything bar=1 baz=0 nowhere nothing=indeed beep=off derp=no nobody=0")

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

        # test the getbool() method - presence
        self.assertTrue(ka.getbool("blah"))  # is present
        self.assertTrue(ka.getbool("foo"))  # has any value

        # test the getbool() method - simple names and values
        self.assertTrue(ka.getbool("bar"))  # 1
        self.assertFalse(ka.getbool("baz"))  # 0
        self.assertFalse(ka.getbool("beep"))  # off
        self.assertFalse(ka.getbool("derp"))  # no

        # test the getbool() method - the super magical "no" prefix
        self.assertFalse(ka.getbool("where"))  # is present with no-prefix
        self.assertFalse(ka.getbool("thing"))  # is set and has no-prefix
        self.assertTrue(ka.getbool("nothing"))  # full name incl. the "no" prefix = is present
        self.assertFalse(ka.getbool("nobody"))  # full name incl. the "no" prefix, value is 0
        self.assertFalse(ka.get("body"))  # no-prefix and has a value

    def real_parsing_and_adding_test(self):
        """Test file spec handling in KernelArguments."""

        ka = KernelArguments()
        self.assertEqual(ka.read(["/proc/cmdlin*", "/nonexistent/file"]), ["/proc/cmdline"])
        self.assertEqual(ka.read("/another/futile/attempt"), [])
        self.assertTrue(ka.getbool("root"))  # expect this to be set in most environments

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

    def shared_instance_test(self):
        """Test the kernel.kernel_arguments instance."""
        self.assertTrue("root" in kernel_arguments)
