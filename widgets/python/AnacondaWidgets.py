from ..importer import modules
from ..overrides import override

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
    def __init__(self, description, kind, capacity, os=None, popup=None):
        Anaconda.DiskOverview.__init__(self)
        self.set_property("description", description)
        self.set_property("kind", kind)
        self.set_property("capacity", capacity)

        if os:
            self.set_property("os", os)

        if popup:
            self.set_property("popup-info", popup)

DiskOverview = override(DiskOverview)
__all__.append('DiskOverview')
