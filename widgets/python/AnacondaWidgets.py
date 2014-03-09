#
# Copyright (C) 2011-2013  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author: Chris Lumens <clumens@redhat.com>
#

"""
These classes and methods wrap the bindings automatically created by
gobject-introspection.  They allow for creating more pythonic bindings
where necessary.  For instance instead of creating a class and then
setting a bunch of properties, these classes allow passing the properties
at creation time.
"""
from gi.importer import modules
from gi.overrides import override

Anaconda = modules['AnacondaWidgets']._introspection_module
__all__ = []

class MountpointSelector(Anaconda.MountpointSelector):
    def __init__(self, name=None, size=None, mountpoint=None):
        Anaconda.MountpointSelector.__init__(self)

        if name:
            self.set_property("name", name)

        if size:
            self.set_property("size", size)

        if mountpoint:
            self.set_property("mountpoint", mountpoint)

        # our extensions not related to the look of the widget
        self._device = None
        self._root = None

    @property
    def size(self):
        return self.get_property("size")

    @size.setter
    def size(self, size):
        self.set_property("size", size)

    @property
    def device(self):
        return self._device

    @device.setter
    def device(self, device):
        self._device = device

    @property
    def root(self):
        return self._root

    @root.setter
    def root(self, dev):
        self._root = dev

MountpointSelector = override(MountpointSelector)
__all__.append('MountpointSelector')

class SpokeSelector(Anaconda.SpokeSelector):
    def __init__(self, title=None, icon=None, status=None):
        Anaconda.SpokeSelector.__init__(self)

        if title:
            self.set_property("title", title)

        if icon:
            self.set_property("icon", icon)

        if status:
            self.set_property("status", status)

SpokeSelector = override(SpokeSelector)
__all__.append('SpokeSelector')

class DiskOverview(Anaconda.DiskOverview):
    def __init__(self, description, kind, capacity, free, name, popup=None):
        Anaconda.DiskOverview.__init__(self)
        self.set_property("description", description)
        self.set_property("kind", kind)
        self.set_property("free", free)
        self.set_property("capacity", capacity)
        self.set_property("name", name)

        if popup:
            self.set_property("popup-info", popup)

DiskOverview = override(DiskOverview)
__all__.append('DiskOverview')
