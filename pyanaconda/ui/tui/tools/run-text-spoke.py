#!/usr/bin/python

import sys, os
import os.path

# Check command line arguments
if len(sys.argv)<2:
    print "Usage: $0 <spoke module name> [<spoke widget class>]"
    sys.exit(1)

# Logging always needs to be set up first thing, or there'll be tracebacks.
from pyanaconda import anaconda_log
anaconda_log.init()

from pyanaconda.installclass import DefaultInstall
from blivet import Blivet
from pyanaconda.threads import initThreading
from pyanaconda.packaging.yumpayload import YumPayload
from pykickstart.version import makeVersion
from pyanaconda.ui.tui.simpleline import App
from pyanaconda.ui.tui import YesNoDialog

# Don't worry with fcoe, iscsi, dasd, any of that crud.
from pyanaconda.flags import flags
flags.imageInstall = True
flags.testing = True

initThreading()

# Figure out the part we are about to show: hub/spoke?
# And get the name of the module which represents it
if os.path.basename(sys.argv[0]) == "run-text-spoke.py":
    spokeModuleName = "pyanaconda.ui.tui.spokes.%s" % sys.argv[1]
    from pyanaconda.ui.common import Spoke
    spokeBaseClass = Spoke
    spokeText = "spoke"
    SpokeText = "Spoke"
elif os.path.basename(sys.argv[0]) == "run-text-hub.py":
    spokeModuleName = "pyanaconda.ui.tui.hubs.%s" % sys.argv[1]
    from pyanaconda.ui.common import Hub
    spokeBaseClass = Hub
    spokeText = "hub"
    SpokeText = "Hub"
else:
    print "You have to run this command as run-spoke.py or run-hub.py."
    sys.exit(1)

# Set default spoke class
spokeClass = None
spokeClassName = None

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
            print k,v
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
app = App("TEST HARNESS", yes_or_no_question = YesNoDialog)

payload = YumPayload(ksdata)
payload.setup(storage)
payload.install_log = sys.stdout

spoke = spokeClass(app, ksdata, storage, payload, instclass)

if not spoke.showable:
    print "This %s is not showable, but I'll continue anyway." % spokeText

app.schedule_screen(spoke)
app.run()

if hasattr(spoke, "status"):
    print "%s status:\n%s\n" % (SpokeText, spoke.status)
if hasattr(spoke, "completed"):
    print "%s completed:\n%s\n" % (SpokeText, spoke.completed)
print "%s kickstart fragment:\n%s" % (SpokeText, ksdata)
