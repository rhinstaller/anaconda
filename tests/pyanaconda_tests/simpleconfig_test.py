# -*- coding: utf-8 -*-
#
# Copyright (C) 2014-2015 Red Hat, Inc.
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
# Red Hat Author(s): Brian C. Lane <bcl@redhat.com>

# Ignore any interruptible calls
# pylint: disable=interruptible-system-call

from pyanaconda.simpleconfig import SimpleConfigFile
from pyanaconda.simpleconfig import simple_replace
from pyanaconda import simpleconfig
import unittest
import tempfile

class SimpleConfigTests(unittest.TestCase):
    TEST_CONFIG = """ESSID="Example Network #1"
ESSID2="Network #2" # With a comment
COMMENT="Save this string" # Strip this comment
#SKIP=Skip this commented line
BOOT=always
KEY=VALUE # Comment "with quotes"
KEY2="A single ' inside" # And comment "with quotes"
"""

    def comment_test(self):
        with tempfile.NamedTemporaryFile(mode="wt") as testconfig:
            testconfig.write(self.TEST_CONFIG)
            testconfig.flush()

            config = SimpleConfigFile(testconfig.name)
            config.read()
            self.assertEqual(config.get("ESSID"), "Example Network #1")
            self.assertEqual(config.get("ESSID2"), "Network #2")
            self.assertEqual(config.get("COMMENT"), "Save this string")
            self.assertEqual(str(config), self.TEST_CONFIG)

    def unquote_test(self):
        self.assertEqual(simpleconfig.unquote("plain string"), "plain string")
        self.assertEqual(simpleconfig.unquote('"double quote"'), "double quote")
        self.assertEqual(simpleconfig.unquote("'single quote'"), "single quote")

    def quote_test(self):
        self.assertEqual(simpleconfig.quote("nospaces"), "nospaces")
        self.assertEqual(simpleconfig.quote("plain string"), '"plain string"')
        self.assertEqual(simpleconfig.quote("alwaysquote", always=True), '"alwaysquote"')

    def set_and_get_test(self):
        """Setting and getting values"""
        scf = SimpleConfigFile()
        scf.set(('key1', 'value1'))
        self.assertEqual(scf.get('key1'), 'value1')
        scf.set(('KEY2', 'value2'))
        self.assertEqual(scf.get('key2'), 'value2')
        scf.set(('KEY3', 'value3'))
        self.assertEqual(scf.get('KEY3'), 'value3')
        scf.set(('key4', 'value4'))
        self.assertEqual(scf.get('KEY4'), 'value4')

    def unset_test(self):
        scf = SimpleConfigFile()
        scf.set(('key1', 'value1'))
        scf.unset(('key1'))
        self.assertEqual(scf.get('key1'), '')

    def write_test(self):
        with tempfile.NamedTemporaryFile(mode="wt") as testconfig:
            scf = SimpleConfigFile()
            scf.set(('key1', 'value1'))
            scf.write(testconfig.name)
            testconfig.flush()
            self.assertEqual(open(testconfig.name).read(), 'KEY1=value1\n')

    def read_test(self):
        with tempfile.NamedTemporaryFile(mode="wt") as testconfig:
            scf = SimpleConfigFile()
            open(testconfig.name, 'w').write('KEY1="value1"\n')
            testconfig.flush()
            scf.read(testconfig.name)
            self.assertEqual(scf.get('key1'), 'value1')

    def read_write_test(self):
        with tempfile.NamedTemporaryFile(mode="wt") as testconfig:
            testconfig.write(self.TEST_CONFIG)
            testconfig.flush()

            scf = SimpleConfigFile()
            scf.read(testconfig.name)
            scf.write(testconfig.name)
            testconfig.flush()
            self.assertEqual(open(testconfig.name).read(), self.TEST_CONFIG)

    def write_new_keys_test(self):
        with tempfile.NamedTemporaryFile(mode="wt") as testconfig:
            testconfig.write(self.TEST_CONFIG)
            testconfig.flush()

            scf = SimpleConfigFile()
            scf.read(testconfig.name)
            scf.set(("key1", "value1"))
            scf.write(testconfig.name)
            testconfig.flush()

            self.assertEqual(open(testconfig.name).read(),
                             self.TEST_CONFIG+"KEY1=value1\n")

    def remove_key_test(self):
        with tempfile.NamedTemporaryFile(mode="wt") as testconfig:
            testconfig.write(self.TEST_CONFIG)
            testconfig.flush()

            scf = SimpleConfigFile()
            scf.read(testconfig.name)
            self.assertEqual(scf.get("BOOT"), "always")
            scf.unset("BOOT")
            scf.write(testconfig.name)
            testconfig.flush()
            scf.reset()
            scf.read(testconfig.name)
            self.assertEqual(scf.get("BOOT"), "")

    def use_tmp_test(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as testconfig:
            # Write a starting file and keep the handle open
            testconfig.write("KEY1=value1\n")
            testconfig.flush()
            testconfig.seek(0)

            # Overwrite the value and write a new file
            scf = SimpleConfigFile()
            scf.read(testconfig.name)
            scf.set(('key1', 'value2'))
            scf.write(testconfig.name, use_tmp=True)

            # Check the new contents
            self.assertEqual(open(testconfig.name).read(), 'KEY1=value2\n')

            # Check that the original file handle still points to the old contents
            self.assertEqual(testconfig.read(), 'KEY1=value1\n')

    def use_tmp_multifs_test(self):
        # Open a file on a non-default filesystem
        with tempfile.NamedTemporaryFile(dir='/dev/shm', mode='w+t') as testconfig:
            # Write a starting file and keep the handle open
            testconfig.write("KEY1=value1\n")
            testconfig.flush()
            testconfig.seek(0)

            # Overwrite the value and write a new file
            scf = SimpleConfigFile()
            scf.read(testconfig.name)
            scf.set(('key1', 'value2'))
            scf.write(testconfig.name, use_tmp=True)

            # Check the new contents
            self.assertEqual(open(testconfig.name).read(), 'KEY1=value2\n')

            # Check that the original file handle still points to the old contents
            self.assertEqual(testconfig.read(), 'KEY1=value1\n')

    def no_use_tmp_test(self):
        with tempfile.NamedTemporaryFile(mode="w+t") as testconfig:
            # Write a starting file and keep the handle open
            testconfig.write("KEY1=value1\n")
            testconfig.flush()
            testconfig.seek(0)

            # Overwrite the value and write a new file
            scf = SimpleConfigFile()
            scf.read(testconfig.name)
            scf.set(('key1', 'value2'))
            scf.write(testconfig.name, use_tmp=False)

            # Check the new contents
            self.assertEqual(open(testconfig.name).read(), 'KEY1=value2\n')

            # Check that the original file handle points to the replaced contents
            self.assertEqual(testconfig.read(), 'KEY1=value2\n')

class SimpleReplaceTests(unittest.TestCase):
    TEST_CONFIG = """#SKIP=Skip this commented line
BOOT=always
"""

    def replace_test(self):
        with tempfile.NamedTemporaryFile(mode="wt") as testconfig:
            testconfig.write(self.TEST_CONFIG)
            testconfig.flush()

            keys = [("BOOT", "BOOT=never")]
            simple_replace(testconfig.name, keys)

            config = SimpleConfigFile(testconfig.name)
            config.read()
            self.assertEqual(config.get("BOOT"), "never")

    def append_test(self):
        with tempfile.NamedTemporaryFile(mode="wt") as testconfig:
            testconfig.write(self.TEST_CONFIG)
            testconfig.flush()

            keys = [("NEWKEY", "NEWKEY=froboz")]
            simple_replace(testconfig.name, keys)

            config = SimpleConfigFile(testconfig.name)
            config.read()
            self.assertEqual(config.get("NEWKEY"), "froboz")

    def no_append_test(self):
        with tempfile.NamedTemporaryFile(mode="wt") as testconfig:
            testconfig.write(self.TEST_CONFIG)
            testconfig.flush()

            keys = [("BOOT", "BOOT=sometimes"), ("NEWKEY", "NEWKEY=froboz")]
            simple_replace(testconfig.name, keys, add=False)

            config = SimpleConfigFile(testconfig.name)
            config.read()
            self.assertEqual(config.get("BOOT"), "sometimes")
            self.assertEqual(config.get("NEWKEY"), "")
