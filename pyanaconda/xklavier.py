#
# Copyright (C) 2012  Red Hat, Inc.
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
# Red Hat Author(s): Martin Gracik <mgracik@redhat.com>
#                    Vratislav Podzimek <vpodzime@redhat.com>
#

"""
This module wraps the libxklavier functionality to protect Anaconda
from dealing with its "nice" API that looks like a Lisp-influenced
"good old C".

It provides a XklWrapper class with several methods that can be used
for listing and various modifications of keyboard layouts settings.
"""

from gi.repository import Xkl, Gdk, GdkX11

def item_str(s):
    """Convert a zero-terminated byte array to a proper str"""

    i = s.find(b'\x00')
    return s[:i].decode("utf-8") #there are some non-ascii layout descriptions

class _Variant(object):
    """Internal class representing a single layout variant"""

    def __init__(self, name, desc):
        self.name = name
        self.desc = desc

    def __str__(self):
        return '%s (%s)' % (self.name, self.desc)

    @property
    def description(self):
        return self.desc

class XklWrapper(object):
    """Class wrapping the libxklavier functionality"""

    def __init__(self):
        #initialize Xkl-related stuff
        display = GdkX11.x11_get_default_xdisplay()
        engine = Xkl.Engine.get_instance(display)
        self._configreg = Xkl.ConfigRegistry.get_instance(engine)
        self._configreg.load(False)

        self._language_keyboard_variants = dict()
        self._country_keyboard_variants = dict()

    def get_variant(self, c_reg, item, subitem, user_data=None):
        variants = list()

        if subitem:
            variants.append(_Variant(item_str(subitem.name), item_str(subitem.description)))
        else:
            variants.append(_Variant(item_str(item.name), item_str(item.description)))

        self._variants_list.append(variants)

    def get_language_variants(self, c_reg, item, user_data=None):
        #helper "global" variable
        self._variants_list = list()
        lang_name, lang_desc = item_str(item.name), item_str(item.description)

        c_reg.foreach_language_variant(lang_name, self.get_variant, None)

        self._language_keyboard_variants[(lang_name, lang_desc)] = self._variants_list

    def get_country_variants(self, c_reg, item, user_data=None):
        #helper "global" variable
        self._variants_list = list()
        country_name, country_desc = item_str(item.name), item_str(item.description)

        c_reg.foreach_country_variant(country_name, self.get_variant, None)

        self._country_keyboard_variants[(country_name, country_desc)] = self._variants_list

    def get_available_layouts(self):
        """A generator yielding layouts (no need to store them as a bunch)"""
        self._configreg.foreach_language(self.get_language_variants, None)

        for (lang_name, lang_desc), variants in sorted(self._language_keyboard_variants.items()):
            for variant in variants:
                for layout in variant:
                    yield "%s (%s)" % (lang_desc.encode("utf-8"), layout.description.encode("utf-8"))

