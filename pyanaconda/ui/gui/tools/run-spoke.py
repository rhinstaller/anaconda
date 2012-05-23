#!/usr/bin/python

from gi.repository import AnacondaWidgets, Gtk
import ctypes, sys

# Check command line arguments
if len(sys.argv)<2:
    print "Usage: $0 <spoke module name> [<spoke widget class>]"
    sys.exit(1)

# This is a hack to make sure the AnacondaWidgets library gets loaded
ctypes.CDLL("libAnacondaWidgets.so.0", ctypes.RTLD_GLOBAL)

# Logging always needs to be set up first thing, or there'll be tracebacks.
from pyanaconda import anaconda_log
anaconda_log.init()

from pyanaconda.installclass import DefaultInstall
from pyanaconda.storage import Storage
from pyanaconda.threads import initThreading
from pyanaconda.packaging.yumpayload import YumPayload
from pyanaconda.platform import getPlatform
from pykickstart.version import makeVersion

# Don't worry with fcoe, iscsi, dasd, any of that crud.
from pyanaconda.flags import flags
flags.imageInstall = True
flags.testing = True

initThreading()

# Figure out the name of spoke module entered on command line
spokeModuleName = "pyanaconda.ui.gui.spokes.%s" % sys.argv[1]

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
    from pyanaconda.ui.gui.spokes import NormalSpoke
    for k,v in vars(spokeModule).iteritems():
        try:
            if issubclass(v, NormalSpoke):
                spokeClassName = k
                spokeClass = v
                break
        except TypeError:
            pass
    
if not spokeClass:
    try:
        spokeClass = getattr(spokeModule, spokeClassName)
    except KeyError:
        print "Spoke %s could not be found in %s" % (spokeClassName, spokeModuleName)
        sys.exit(1)


print "Running spoke %s from %s" % (spokeClass, spokeModule)

platform = getPlatform()
ksdata = makeVersion()
storage = Storage(data=ksdata, platform=platform)
storage.reset()
instclass = DefaultInstall()

payload = YumPayload(ksdata)
payload.setup(storage)
payload.install_log = sys.stdout

if not spokeClass:
    print "You forgot to set spokeClass to something."
    sys.exit(1)

spoke = spokeClass(ksdata, storage, payload, instclass)
if hasattr(spoke, "register_event_cb"):
    spoke.register_event_cb("continue", lambda: Gtk.main_quit())
    spoke.register_event_cb("quit", lambda: Gtk.main_quit())
spoke.initialize()

if not spoke.showable:
    print "This spoke is not showable, but I'll continue anyway."

spoke.refresh()
spoke.window.set_beta(True)
spoke.window.set_property("distribution", "TEST HARNESS")
spoke.window.show_all()

Gtk.main()

if hasattr(spoke, "status"):
    print "Spoke status:\n%s\n" % spoke.status
print "Spoke completed:\n%s\n" % spoke.completed
print "Spoke kickstart fragment:\n%s" % ksdata
