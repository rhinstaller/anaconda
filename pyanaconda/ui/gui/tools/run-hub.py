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
from pykickstart.version import makeVersion

# Don't worry with fcoe, iscsi, dasd, any of that crud.
from pyanaconda.flags import flags
flags.imageInstall = True
flags.testing = True

initThreading()

# NOTE:  To run your hub, you need to do the proper import here (may need to
# set $PYTHONPATH as well) and set hubClass to be the class from that import.
# I suppose this could be done automatically somehow, but that's hard and this
# is a development testing tool.
#from pyanaconda.ui.gui.hubs.summary import SummaryHub
#hubClass = SummaryHub
hubClass = None

storage = Storage()
storage.reset()

ksdata = makeVersion()
devicetree = storage.devicetree
instclass = DefaultInstall()

if not hubClass:
    print "You forgot to set hubClass to something."
    sys.exit(1)

hub = hubClass(ksdata, devicetree, instclass)
hub.register_event_cb("continue", lambda: Gtk.main_quit())
hub.register_event_cb("quit", lambda: Gtk.main_quit())
hub.populate()

if not hub.showable:
    print "This hub is not showable, but I'll continue anyway."

hub.setup()
hub.window.set_beta(True)
hub.window.set_property("distribution", "TEST HARNESS")
hub.window.show_all()

Gtk.main()

print "Hub kickstart fragment:\n%s" % ksdata
