#
# exception.py - general exception formatting and saving
#
# Matt Wilson <msw@redhat.com>
# Erik Troan <ewt@redhat.com>
#
# Copyright 2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import isys
import os
import signal
import traceback
import iutil
import types
from string import joinfields
from cPickle import Pickler
from translate import _
from flags import flags

dumpHash = {}

def dumpClass(instance, fd, level=0):
    # protect from loops
    if not dumpHash.has_key(instance):
        dumpHash[instance] = None
    else:
        fd.write("Already dumped\n")
        return
    fd.write("%s instance, containing members:\n" %
             (instance.__class__.__name__))
    pad = ' ' * ((level) * 2)
    for key, value in instance.__dict__.items():
        if type(value) == types.InstanceType:
            fd.write("%s%s: " % (pad, key))
            dumpClass(value, fd, level + 1)
        else:
            fd.write("%s%s: %s\n" % (pad, key, value))

def dumpException(out, text, tb, dispatch):
    p = Pickler(out)

    out.write(text)

    trace = tb
    while trace.tb_next:
        trace = trace.tb_next
    frame = trace.tb_frame
    out.write ("\nLocal variables in innermost frame:\n")
    try:
        for (key, value) in frame.f_locals.items():
            out.write ("%s: %s\n" % (key, value))
    except:
        pass

    # these have C objects in them which can't dump
    dispatch.id.hdList = None
    dispatch.id.comps = None

#    dispatch.intf = None
#    dispatch.dispatch = None

    # we don't need to know passwords
    dispatch.id.rootPassword = None
    dispatch.id.accounts = None

    try:
        out.write("\n\n")
        dumpClass(dispatch, out)
    except:
        out.write("Exception occured during state dump\n")

def handleException(dispatch, intf, (type, value, tb)):
    list = traceback.format_exception (type, value, tb)
    text = joinfields (list, "")
    rc = intf.exceptionWindow (_("Exception Occurred"), text)
    if rc == 1:
	intf.__del__ ()
        print text
        import pdb
        pdb.post_mortem (tb)
        os.kill(os.getpid(), signal.SIGKILL)
    elif not rc:
	intf.__del__ ()
        os.kill(os.getpid(), signal.SIGKILL)

    if not flags.setupFilesystems:
        out = open("/tmp/anacdump.txt", "w")
        dumpException (out, text, tb, dispatch)
        out.close()
        intf.__del__ ()
        os.kill(os.getpid(), signal.SIGKILL)

    while 1:
	rc = intf.dumpWindow()
	if rc:
	    intf.__del__ ()
            os.kill(os.getpid(), signal.SIGKILL)

	device = id.floppyDevice
	file = "/tmp/floppy"
        try:
            isys.makeDevInode(device, file)
        except SystemError:
            pass
	try:
	    fd = os.open(file, os.O_RDONLY)
	except:
	    continue

	os.close(fd)

	if iutil.getArch() != "ia64":
	    args = [ 'mkdosfs', '/tmp/floppy' ]

	
	    cmd = "/usr/sbin/mkdosfs"
	
	    if os.access("/sbin/mkdosfs", os.X_OK):
		cmd = "/sbin/mkdosfs"


	    iutil.execWithRedirect (cmd, args, 
                                stdout = '/dev/tty5', stderr = '/dev/tty5')
				
        try:
            isys.mount(device, "/tmp/crash", fstype = "vfat")
        except SystemError:
            continue

	out = open("/tmp/crash/anacdump.txt", "w")
        dumpException (out, text, tb, dispatch)
        out.close()

        # write out any syslog information as well
        try:
            iutil.copyFile("/tmp/syslog", "/tmp/crash")
        except:
            pass
        
	isys.umount("/tmp/crash")

	intf.messageWindow(_("Dump Written"),
	    _("Your system's state has been successfully written to the "
	      "floppy. Your system will now be reset."))

	intf.__del__ ()
        os.kill(os.getpid(), signal.SIGKILL)
