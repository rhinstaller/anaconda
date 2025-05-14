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
#

from unittest import TestCase

from gladecheck import check_glade_files


class CheckTranslatableComponents(TestCase):
    def test_translatable_treeview(self):
        """Check that unshown GtkTreeview column headers are not translatable."""
        check_glade_files(self, self._check_translatable_treeview)

    def _check_translatable_treeview(self, glade_tree):
        """Check that unshown GtkTreeview column headers are not translatable.

           These values are not displayed and should not be translated.
        """

        # Look for
        # <object class="GtkTreeView">
        #   <property name="headers_visible">False</property>
        #   ...
        #   <child>
        #     <object class="GtkTreeViewColumn">
        #       <property name="title" translatable="yes">...

        for translatable in glade_tree.xpath(".//object[@class='GtkTreeView' and ./property[@name='headers_visible' and ./text() = 'False']]/child/object[@class='GtkTreeViewColumn']/property[@name='title' and @translatable='yes']"):
            raise AssertionError("Translatable, hidden column found at %s:%d" % (translatable.base, translatable.sourceline))

    def test_translatable_notebook(self):
        """Check that unshown GtkNotebook tabs are not translatable."""
        check_glade_files(self, self._check_translatable_notebook)

    def _check_translatable_notebook(self, glade_tree):
        """Check that unshown GtkNotebook tabs are not translatable."""

        # Look for
        # <object class="GtkNotebook">
        #   <property name="show_tabs">False</property>
        #   ...
        #   <child type="tab">
        #      ... (probably a GtkLabel but doesn't have to be)
        #       <property name="label" translatable="yes">...
        for translatable in glade_tree.xpath(".//object[@class='GtkNotebook' and ./property[@name='show_tabs' and ./text() = 'False']]/child[@type='tab']//property[@name='label' and @translatable='yes']"):
            raise AssertionError("Translatable, hidden tab found at %s:%d" % (translatable.base, translatable.sourceline))
