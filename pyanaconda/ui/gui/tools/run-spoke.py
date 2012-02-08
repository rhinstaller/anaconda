#!/usr/bin/python

from gi.repository import AnacondaWidgets, Gtk
import ctypes, sys

# This is a hack to make sure the AnacondaWidgets library gets loaded
ctypes.CDLL("libAnacondaWidgets.so.0", ctypes.RTLD_GLOBAL)

# Logging always needs to be set up first thing, or there'll be tracebacks.
from pyanaconda import anaconda_log
anaconda_log.init()

from pyanaconda.installclass import DefaultInstall
from pyanaconda.storage import Storage
from pyanaconda.threads import initThreading
from pyanaconda.platform import getPlatform
from pykickstart.version import makeVersion

# Don't worry with fcoe, iscsi, dasd, any of that crud.
from pyanaconda.flags import flags
flags.imageInstall = True
flags.testing = True

initThreading()

# NOTE:  To run your spoke, you need to do the proper import here (may need to
# set $PYTHONPATH as well) and set spokeClass to be the class from that import.
# I suppose this could be done automatically somehow, but that's hard and this
# is a development testing tool.
#from pyanaconda.ui.gui.spokes.software import SoftwareSelectionSpoke
#spokeClass = SoftwareSelectionSpoke
spokeClass = None

platform = getPlatform()
ksdata = makeVersion()
storage = Storage(data=ksdata, platform=platform)
storage.reset()
devicetree = storage.devicetree
instclass = DefaultInstall()

if not spokeClass:
    print "You forgot to set spokeClass to something."
    sys.exit(1)

spoke = spokeClass(ksdata, devicetree, instclass)
if hasattr(spoke, "register_event_cb"):
    spoke.register_event_cb("continue", lambda: Gtk.main_quit())
    spoke.register_event_cb("quit", lambda: Gtk.main_quit())
spoke.populate()

if not spoke.showable:
    print "This spoke is not showable, but I'll continue anyway."

spoke.setup()
spoke.window.set_beta(True)
spoke.window.set_property("distribution", "TEST HARNESS")
spoke.window.show_all()

Gtk.main()

if hasattr(spoke, "status"):
    print "Spoke status:\n%s\n" % spoke.status
print "Spoke completed:\n%s\n" % spoke.completed
print "Spoke kickstart fragment:\n%s" % ksdata
