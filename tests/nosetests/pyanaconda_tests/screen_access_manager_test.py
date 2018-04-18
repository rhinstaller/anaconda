# vim:set fileencoding=utf-8
#
# Copyright (C) 2016  Red Hat, Inc.
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
# Red Hat Author(s): Martin Kolman <mkolman@redhat.com>
#

import unittest
import tempfile
import shutil
import os
from configparser import ConfigParser

from pyanaconda import screen_access

class ScreenAccessManagerTest(unittest.TestCase):
    """Test the spoke access manager.

    Check that it can correctly handle existing user interaction config files,
    correctly handle spoke visits and option changes, state querying and
    that the config files it creates are valid.
    """

    def _get_config_path(self):
        test_dir = tempfile.mkdtemp()
        config_path = os.path.join(test_dir, screen_access.CONFIG_FILE_NAME)
        return test_dir, config_path

    def _parse_config_file(self, config_path):
        config = ConfigParser()
        with open(config_path, "rt") as f:
            config.read_file(f)
        return config

    def file_header_test(self):
        """Test that the Anaconda generated config file header looks fine."""
        screen_access.initSAM()
        sam = screen_access.sam
        header = sam._get_new_config_header()
        # check that the header starts with a hash
        self.assertEqual(header[0], "#")
        # check that it has a newline at the end
        self.assertEqual(header[-1], "\n")

    def no_interaction_test(self):
        """Test that SAM can handle no user interaction taking place."""
        screen_access.initSAM()
        sam = screen_access.sam

        try:
            test_dir, config_path = self._get_config_path()
            sam.write_out_config_file(os.path.join(test_dir, screen_access.CONFIG_FILE_NAME))
            self.assertTrue(os.path.exists(config_path))
            # the config should have the "created by Anaconda" header, so it should
            # be non-zero
            self.assertGreater(os.path.getsize(config_path), 0)
        finally:
            shutil.rmtree(test_dir)

    def spoke_visited_test(self):
        """Test that SAM correctly marks a spoke as visited in the output config."""

        screen_access.initSAM()
        sam = screen_access.sam
        try:
            test_dir, config_path = self._get_config_path()
            # mark a screen as visited
            sam.mark_screen_visited("FooSpoke")
            # it should be safe to mark a screen as visited multiple times
            sam.mark_screen_visited("FooSpoke")
            # write the config file
            sam.write_out_config_file(os.path.join(test_dir, screen_access.CONFIG_FILE_NAME))
            # the resulting config file needs to exist and be non-empty
            self.assertTrue(os.path.exists(config_path))
            self.assertGreater(os.path.getsize(config_path), 0)
            # parse the file and check if it contains the FooSpoke section
            # and visited key set to 0

            config = self._parse_config_file(config_path)
            self.assertTrue(config.has_section("FooSpoke"))
            self.assertEqual(config.get("FooSpoke", screen_access.CONFIG_VISITED_KEY), screen_access.CONFIG_TRUE)
        finally:
            shutil.rmtree(test_dir)

    def spoke_option_changed_test(self):
        """Test that SAM correctly marks option as changed in the output config."""
        screen_access.initSAM()
        sam = screen_access.sam
        try:
            test_dir, config_path = self._get_config_path()
            # mark a screen as visited
            sam.mark_screen_visited("FooSpoke")
            # mark some options on it as changed
            sam.mark_screen_option_changed("FooSpoke", "BarOption")
            sam.mark_screen_option_changed("FooSpoke", "BazOption")
            # it should be possible to mark an option as changed multiple
            # times so that Anaconda doesn't have to check before marking
            # an option as changed
            sam.mark_screen_option_changed("FooSpoke", "BarOption")
            sam.mark_screen_option_changed("FooSpoke", "BazOption")
            # check if SAM correctly reports the options as changed
            self.assertTrue(sam.get_screen_option_changed("FooSpoke", "BarOption"))
            self.assertTrue(sam.get_screen_option_changed("FooSpoke", "BazOption"))

            # try marking something as changed on a spoke
            # that has not been visited
            sam.mark_screen_option_changed("UnvisitedSpoke", "UnaccessibleOption")
            # the option should still be marked as not changed
            self.assertFalse(sam.get_screen_option_changed("UnvisitedSpoke", "UnaccessibleOption"))

            # now write out the config and check if it is valid
            sam.write_out_config_file(os.path.join(test_dir, screen_access.CONFIG_FILE_NAME))

            config = self._parse_config_file(config_path)
            self.assertTrue(config.has_section("FooSpoke"))
            self.assertEqual(config.get("FooSpoke", screen_access.CONFIG_VISITED_KEY), screen_access.CONFIG_TRUE)
            self.assertEqual(config.get("FooSpoke", screen_access.CONFIG_OPTION_PREFIX + "BarOption"), screen_access.CONFIG_TRUE)
            self.assertEqual(config.get("FooSpoke", screen_access.CONFIG_OPTION_PREFIX + "BazOption"), screen_access.CONFIG_TRUE)
            # make sure there is no "UnvisitedSpoke" in the config
            self.assertFalse(config.has_section("UnvisitedSpoke"))
            self.assertEqual(config.get("UnivisitedSpoke", screen_access.CONFIG_OPTION_PREFIX + "UnaccessibleOption", fallback=None), None)
        finally:
            shutil.rmtree(test_dir)

    def disale_post_install_tools_test(self):
        """Test that SAM can correctly disable post install tools via the user interaction config."""
        screen_access.initSAM()
        sam = screen_access.sam

        try:
            test_dir, config_path = self._get_config_path()
            # post install tools should be enabled by default
            self.assertFalse(sam.post_install_tools_disabled)
            # set post install tools to disabled
            sam.post_install_tools_disabled = True
            # check if SAM correctly reports the change
            self.assertTrue(sam.post_install_tools_disabled)
            sam.write_out_config_file(os.path.join(test_dir, screen_access.CONFIG_FILE_NAME))
            # check if the option is correctly reflected in the
            # user interaction config file
            config = self._parse_config_file(config_path)
            self.assertTrue(config.has_section(screen_access.CONFIG_GENERAL_SECTION))
            self.assertEqual(config.get(screen_access.CONFIG_GENERAL_SECTION, screen_access.CONFIG_DISABLE_POSTINST_TOOLS_KEY),
                             screen_access.CONFIG_TRUE)
        finally:
            shutil.rmtree(test_dir)

    def existing_config_test(self):
        """Test that SAM can correctly parse an existing user interaction config."""
        screen_access.initSAM()
        sam = screen_access.sam
        try:
            test_dir, config_path = self._get_config_path()
            third_party_config = """
# Generated by some third party tool

[General]
# disable post install tools
post_install_tools_disabled=1

[FooScreen]
visited=1

[BarScreen]
visited=1
# some options have been changed
changed_some_option=1
changed_other_option=1
# these options use wrong boolean syntax
# (only 1 and 0 is allowed by the spec)
changed_bad_syntax_1=yes
changed_bad_syntax_2=true
changed_bad_syntax_3=True
changed_bad_syntax_4=no
changed_bad_syntax_5=false
changed_bad_syntax_6=False
changed_bad_syntax_7=2
changed_bad_syntax_8=something

# a random keys that should be ignored
not_an_option=1
not_changed=abc
"""
            with open(config_path, "wt") as f:
                f.write(third_party_config)

            sam.open_config_file(config_path)
            # check that SAM has correctly parsed the config file
            self.assertTrue(sam.post_install_tools_disabled)
            self.assertTrue(sam.get_screen_visited("FooScreen"))
            self.assertTrue(sam.get_screen_visited("BarScreen"))
            self.assertTrue(sam.get_screen_option_changed("BarScreen", "some_option"))
            self.assertTrue(sam.get_screen_option_changed("BarScreen", "other_option"))
            # options using bad boolean syntax should be ignored
            self.assertFalse(sam.get_screen_option_changed("BarScreen", "bad_syntax_1"))
            self.assertFalse(sam.get_screen_option_changed("BarScreen", "bad_syntax_2"))
            self.assertFalse(sam.get_screen_option_changed("BarScreen", "bad_syntax_3"))
            self.assertFalse(sam.get_screen_option_changed("BarScreen", "bad_syntax_4"))
            self.assertFalse(sam.get_screen_option_changed("BarScreen", "bad_syntax_5"))
            self.assertFalse(sam.get_screen_option_changed("BarScreen", "bad_syntax_6"))
            self.assertFalse(sam.get_screen_option_changed("BarScreen", "bad_syntax_7"))
            self.assertFalse(sam.get_screen_option_changed("BarScreen", "bad_syntax_8"))
            # those other two keys don̈́'t have the changed prefix, so should not be parsed
            # as changed options
            self.assertFalse(sam.get_screen_option_changed("BarScreen", "not_an_option"))
            self.assertFalse(sam.get_screen_option_changed("BarScreen", "not_changed"))

            # now try changing more stuff and then check if it correctly propagates
            # to the resulting user interaction config file

            # lets say the user changed something else on the BarScreen
            sam.mark_screen_option_changed("BarScreen", "option_changed_in_anaconda")
            # and then visited the BazScreen and also changed something on it
            sam.mark_screen_visited("BazScreen")
            sam.mark_screen_option_changed("BazScreen", "baz_option_1")
            sam.mark_screen_option_changed("BazScreen", "baz_option_2")

            # write out the config file and check if it is valid
            sam.write_out_config_file(os.path.join(test_dir, screen_access.CONFIG_FILE_NAME))
            config = self._parse_config_file(config_path)

            self.assertTrue(config.has_section(screen_access.CONFIG_GENERAL_SECTION))
            self.assertTrue(config.get(screen_access.CONFIG_GENERAL_SECTION,
                                       screen_access.CONFIG_DISABLE_POSTINST_TOOLS_KEY),
                            screen_access.CONFIG_TRUE)

            self.assertTrue(config.has_section("FooScreen"))
            self.assertEqual(config.get("FooScreen", screen_access.CONFIG_VISITED_KEY), screen_access.CONFIG_TRUE)

            self.assertTrue(config.has_section("BarScreen"))
            self.assertEqual(config.get("BarScreen", screen_access.CONFIG_OPTION_PREFIX + "some_option"), screen_access.CONFIG_TRUE)
            self.assertEqual(config.get("BarScreen", screen_access.CONFIG_OPTION_PREFIX + "other_option"), screen_access.CONFIG_TRUE)
            self.assertEqual(config.get("BarScreen", screen_access.CONFIG_OPTION_PREFIX + "option_changed_in_anaconda"), screen_access.CONFIG_TRUE)

            self.assertTrue(config.has_section("BazScreen"))
            self.assertEqual(config.get("BazScreen", screen_access.CONFIG_OPTION_PREFIX + "baz_option_1"), screen_access.CONFIG_TRUE)
            self.assertEqual(config.get("BazScreen", screen_access.CONFIG_OPTION_PREFIX + "baz_option_2"), screen_access.CONFIG_TRUE)
        finally:
            shutil.rmtree(test_dir)
