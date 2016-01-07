# Check that a string does not contain unnecessary Pango markup
#
# Copyright (C) 2015  Red Hat, Inc.
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
# Red Hat Author(s): David Shea <dshea@redhat.com>

from pocketlint.pangocheck import is_markup, markup_necessary
import xml.etree.ElementTree as ET

def test_markup(poentry):
    # Unnecessary markup is markup applied to an entire string, such as
    # _("<b>Bold Text</b>"). This could be instead be translated as
    # "<b>%s</b>" % _("Bold Text"), and then the translator doesn't have to see
    # the markup at all.

    if is_markup(poentry.msgid):
        # Wrap the string in <markup> nodes, parse it, test it
        # The markup is unescaped on purpose
        # pylint: disable=unescaped-markup
        tree = ET.fromstring("<markup>%s</markup>" % poentry.msgid)
        if not markup_necessary(tree):
            raise AssertionError("Unnecessary markup")
