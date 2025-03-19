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
# Free Software Foundation, Inc., 31 Milk Street #960789 Boston, MA
# 02196 USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

import unittest
from pyanaconda.core.kernel import KernelArguments, kernel_arguments
import collections


class KernelArgumentsTests(unittest.TestCase):

    def test_value_retrieval(self):
        """KernelArguments value retrieval test."""

        ka = KernelArguments.from_string(
            "inst.blah foo=anything inst.bar=1 baz=0 nowhere inst.nothing=indeed beep=off "
            "derp=no nobody=0")

        # test using "in" operator on the class
        assert "blah" in ka
        assert "foo" in ka
        assert not ("thisisnotthere" in ka)
        assert not ("body" in ka)
        assert "nobody" in ka

        # test the get() method
        assert ka.get("foo") == "anything"
        assert ka.get("thisisnotthere") is None
        assert ka.get("thisisnotthere", "fallback") == "fallback"

        # test the is_enabled() method
        assert ka.is_enabled("blah")  # present
        assert ka.is_enabled("foo")  # any value
        assert ka.is_enabled("bar")  # 1 = any value
        assert not ka.is_enabled("baz")  # 0
        assert ka.is_enabled("nowhere")  # present
        assert ka.is_enabled("nothing")  # present
        assert not ka.is_enabled("beep")  # off
        assert ka.is_enabled("derp")  # no = any value
        assert not ka.is_enabled("nobody")  # 0
        assert not ka.is_enabled("thing")  # not present
        assert not ka.is_enabled("where")  # not present

    def test_real_parsing_and_adding(self):
        """Test file spec handling in KernelArguments."""

        ka = KernelArguments()
        assert ka.read(["/proc/cmdlin*", "/nonexistent/file"]) == ["/proc/cmdline"]
        assert ka.read("/another/futile/attempt") == []

    def test_special_argument_handling(self):
        """Test handling of special arguments in KernelArguments."""

        ka = KernelArguments.from_string("modprobe.blacklist=floppy modprobe.blacklist=reiserfs")
        assert ka.get("modprobe.blacklist") == "floppy reiserfs"
        ka.read_string("inst.addrepo=yum inst.addrepo=dnf")
        assert ka.get("addrepo") == ["yum", "dnf"]
        ka.read_string("inst.ks=kickstart")
        assert ka.get("ks") == "kickstart"

    def test_items(self):
        """Test KernelArguments access to contents with iterator."""

        ka = KernelArguments.from_defaults()
        it = ka.items()
        assert isinstance(it, collections.Iterable)
        root_seen = False
        for k, v in it:  # pylint: disable=unused-variable
            if k == "root":
                root_seen = True
        assert root_seen

    def test_items_raw(self):
        """Test KernelArguments access to raw contents with iterator."""

        ka = KernelArguments.from_string(
            "blah inst.foo=anything inst.nothing=indeed")
        it = ka.items_raw()

        assert isinstance(it, collections.Iterable)

        res = dict()
        for k, v in it:
            res[k] = v

        assert "inst.foo" in res
        assert "blah" in res
        assert "inst.nothing" in res

        assert res["inst.nothing"] == "indeed"

    def test_shared_instance(self):
        """Test the kernel.kernel_arguments instance."""
        assert "root" in kernel_arguments
