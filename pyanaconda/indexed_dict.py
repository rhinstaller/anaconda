# indexed_dict.py
# Implements IndexedDictionary class.
#
# Copyright (C) 2009  Red Hat, Inc.
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

class IndexedDict(dict):
    """ Indexed dictionary that remembers order of the inserted elements.

        Values can be inserted with string keys only, but referenced by both
        string keys or index.

        There's a unit test for the class, please maintain it along.
    """
    def __init__(self):
        super(IndexedDict, self).__init__()
        self._indexes = []

    def __getitem__(self, key):
        if type(key) is int:
            key = self._indexes[key]
        return super(IndexedDict, self).__getitem__(key)

    def __setitem__(self, key, value):
        if type(key) is int:
            raise TypeError("IndexedDict only accepts strings as new keys")
        assert(len(self) == len(self._indexes))
        self._indexes.append(key)
        return super(IndexedDict, self).__setitem__(key, value)

    def index(self, string_key):
        return self._indexes.index(string_key)
