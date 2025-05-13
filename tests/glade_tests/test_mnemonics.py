#
# Copyright (C) 2015  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from unittest import TestCase

from gladecheck import check_glade_files


class CheckMnemonics(TestCase):
    def test_mnemonics(self):
        """Check for widgets with keyboard accelerators but no mnemonic."""
        check_glade_files(self, self._check_mnemonics)

    def _check_mnemonics(self, glade_tree):
        """Check for widgets with keyboard accelerators but no mnemonic"""

        # Look for labels with use-underline=True and no mnemonic-widget
        for label in glade_tree.xpath(".//object[@class='GtkLabel' and ./property[@name='use_underline' and ./text() = 'True'] and not(./property[@name='mnemonic_widget'])]"):
            # And now filter out the cases where the label actually does have a mnemonic.
            # This list is not comprehensive, probably.

            parent = label.getparent()

            # Is the label the child of a GtkButton? The button might be pretty far up there.
            # Assume widget names that end in "Button" are subclasses of GtkButton
            if parent.tag == 'child' and \
                    label.xpath("ancestor::object[substring(@class, string-length(@class) - string-length('Button') + 1) = 'Button']"):
                continue

            # Is the label a GtkNotebook tab?
            if parent.tag == 'child' and parent.get('type') == 'tab' and \
                    parent.getparent().get('class') == 'GtkNotebook':
                continue

            raise AssertionError("Label with accelerator and no mnemonic at %s:%d" % (label.base, label.sourceline))
