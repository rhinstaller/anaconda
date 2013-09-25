#!/usr/bin/python

import sys, os

import gi.overrides

# We need this so we can tell GI to look for overrides objects
# also in anaconda source directories
for p in os.environ.get("ANACONDA_WIDGETS_OVERRIDES", "").split(":"):
    gi.overrides.__path__.insert(0, p)

from gi.repository import Gtk

import ctypes
import os.path

# Check command line arguments
if len(sys.argv)<2:
    print "Usage: $0 <spoke module name> [<spoke widget class>]"
    sys.exit(1)

# This is a hack to make sure the AnacondaWidgets library gets loaded
ctypes.CDLL("libAnacondaWidgets.so.1", ctypes.RTLD_GLOBAL)

# Logging always needs to be set up first thing, or there'll be tracebacks.
from pyanaconda import anaconda_log
anaconda_log.init()

from pyanaconda.installclass import DefaultInstall
from blivet import Blivet
from pyanaconda.threads import initThreading
from pyanaconda.packaging.yumpayload import YumPayload
from pykickstart.version import makeVersion

# Don't worry with fcoe, iscsi, dasd, any of that crud.
from pyanaconda.flags import flags
flags.imageInstall = True
flags.testing = True

initThreading()

# Figure out the part we are about to show: hub/spoke?
# And get the name of the module which represents it
if os.path.basename(sys.argv[0]) == "run-spoke.py":
    spokeModuleName = "pyanaconda.ui.gui.spokes.%s" % sys.argv[1]
    from pyanaconda.ui.common import Spoke
    spokeBaseClass = Spoke
    spokeText = "spoke"
    SpokeText = "Spoke"
elif os.path.basename(sys.argv[0]) == "run-hub.py":
    spokeModuleName = "pyanaconda.ui.gui.hubs.%s" % sys.argv[1]
    from pyanaconda.ui.common import Hub
    spokeBaseClass = Hub
    spokeText = "hub"
    SpokeText = "Hub"
else:
    print "You have to run this command as run-spoke.py or run-hub.py."
    sys.exit(1)

# Set default spoke class
spokeClass = None

# Load spoke specified on the command line
# If the spoke module was specified, but the spoke class was not,
# try to find it using class hierarchy
try:
    spokeClassName = sys.argv[2]
    __import__(spokeModuleName, fromlist = [spokeClassName])
    spokeModule = sys.modules[spokeModuleName]
except IndexError:
    __import__(spokeModuleName)
    spokeModule = sys.modules[spokeModuleName]
    for k,v in vars(spokeModule).iteritems():
        try:
            if issubclass(v, spokeBaseClass) and v != spokeBaseClass:
                spokeClassName = k
                spokeClass = v
        except TypeError:
            pass

if not spokeClass:
    try:
        spokeClass = getattr(spokeModule, spokeClassName)
    except KeyError:
        print "%s %s could not be found in %s" % (SpokeText, spokeClassName, spokeModuleName)
        sys.exit(1)


print "Running %s %s from %s" % (spokeText, spokeClass, spokeModule)

ksdata = makeVersion()
storage = Blivet(ksdata=ksdata)
storage.reset()
instclass = DefaultInstall()

payload = YumPayload(ksdata)
payload.setup(storage)

spoke = spokeClass(ksdata, storage, payload, instclass)
if hasattr(spoke, "register_event_cb"):
    spoke.register_event_cb("continue", Gtk.main_quit)
    spoke.register_event_cb("quit", Gtk.main_quit)

if hasattr(spoke, "set_path"):
    spoke.set_path("categories", [
        ("pyanaconda.ui.gui.categories.%s",
         os.path.join(os.path.dirname(__file__),"..", "categories"))
         ])
    spoke.set_path("spokes", [
        ("pyanaconda.ui.gui.spokes.%s",
         os.path.join(os.path.dirname(__file__), "..", "spokes"))
         ])
    
spoke.initialize()
    
if not spoke.showable:
    print "This %s is not showable, but I'll continue anyway." % spokeText

spoke.refresh()
spoke.window.set_beta(True)
spoke.window.set_property("distribution", "TEST HARNESS")
spoke.window.show_all()

Gtk.main()

if hasattr(spoke, "status"):
    print "%s status:\n%s\n" % (SpokeText, spoke.status)
if hasattr(spoke, "completed"):
    print "%s completed:\n%s\n" % (SpokeText, spoke.completed)
print "%s kickstart fragment:\n%s" % (SpokeText, ksdata)
