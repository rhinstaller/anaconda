#
# exception.py - general exception formatting and saving
#
# Matt Wilson <msw@redhat.com>
# Erik Troan <ewt@redhat.com>
#
# Copyright 2000-2003 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import isys
import sys
import os
import signal
import traceback
import iutil
import types
import rpm
from string import joinfields
from cPickle import Pickler
from rhpl.translate import _
from rhpl.log import log
from flags import flags

dumpHash = {}

# XXX do length limits on obj dumps.
def dumpClass(instance, fd, level=0, parentkey=""):

    keySkipList = [ 
		    "id.accounts",
		    "id.bootloader.password",
		    "id.comps",
		    "id.dispatch",
		    "id.hdList",		    
		    "id.keyboard.modelDict",
		    "intf.icw.buff",
		    "intf.icw.releaseNotesContents",
		    "intf.icw.stockButtons",
		    "id.instLanguage.nativeLangNames",
		    "id.instLanguage.runtimeLangs",
		    "id.instLanguage.langList",
		    "id.instLanguage.langNicks",
		    "id.instLanguage.font",
		    "id.instLanguage.kbd",
		    "id.instLanguage.tz",
		    "id.instLanguage.langInfoByName",
		    "id.instLanguage.langNicks",
		    "id.instLanguage.langList",
		    "id.instLanguage.allSupportedLangs",
		    "id.rootPassword",
		    "id.tmpData",
		    "id.xsetup.xhwstate.monitor.monlist",
		    "id.xsetup.xhwstate.monitor.monids"
		   ]

    # protect from loops
    if not dumpHash.has_key(instance):
        dumpHash[instance] = None
    else:
        fd.write("Already dumped\n")
        return
    if (instance.__class__.__dict__.has_key("__str__") or
        instance.__class__.__dict__.has_key("__repr__")):
        fd.write("%s\n" % (instance,))
        return
    fd.write("%s instance, containing members:\n" %
             (instance.__class__.__name__))
    pad = ' ' * ((level) * 2)

    for key, value in instance.__dict__.items():
	if parentkey != "":
	    curkey = parentkey + "." + key
	else:
	    curkey = key

	if curkey in keySkipList:
	    continue
	    
        if type(value) == types.ListType:
            fd.write("%s%s: [" % (pad, curkey))
            first = 1
            for item in value:
                if not first:
                    fd.write(", ")
                else:
                    first = 0
                if type(item) == types.InstanceType:
                    dumpClass(item, fd, level + 1)
                else:
                    fd.write("%s" % (item,))
            fd.write("]\n")
        elif type(value) == types.DictType:
            fd.write("%s%s: {" % (pad, curkey))
            first = 1
            for k, v in value.items():
		newkey = curkey+"."+str(k)
		if newkey in keySkipList:
		    continue
		
                if not first:
                    fd.write(", ")
                else:
                    first = 0
                if type(k) == types.StringType:
                    fd.write("'%s': " % (k,))
                else:
                    fd.write("%s: " % (k,))
                if type(v) == types.InstanceType:
                    dumpClass(v, fd, level + 1, parentkey = curkey)
                else:
                    fd.write("%s" % (v,))
            fd.write("}\n")
        elif type(value) == types.InstanceType:
            fd.write("%s%s: " % (pad, curkey))
            dumpClass(value, fd, level + 1, parentkey=curkey)
        else:
            fd.write("%s%s: %s\n" % (pad, curkey, value))

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

    if dispatch.id.grpset:
        out.write("\n\nPackage Group selection status:\n")
        for comp in dispatch.id.grpset.groups.values():
            out.write("%s: %s\n" % (comp.name,
                                    comp.isSelected(justManual = 1)))

    if dispatch.id.grpset and dispatch.id.grpset.hdrlist:
        out.write("\n\nIndividual package selection status:\n")
        pkgList = dispatch.id.grpset.hdrlist.pkgs.keys()
        pkgList.sort()
        for pkg in pkgList:
            p = dispatch.id.grpset.hdrlist.pkgs[pkg]
            out.write("%s: %s, " % (p[rpm.RPMTAG_NAME],
                                    p.isSelected()))
        out.write("\n")
    
    # we don't need to know passwords
#    dispatch.id.rootPassword = None
#    dispatch.id.accounts = None

#    dispatch.intf = None
#    dispatch.dispatch = None

#    try:
#        if dispatch.id.xsetup and dispatch.id.xsetup.xhwstate and dispatch.id.xsetup.xhwstate.monitor:
#            dispatch.id.xsetup.xhwstate.monitor.monlist = None
#            dispatch.id.xsetup.xhwstate.monitor.monids = None
#        dispatch.id.instLanguage.langNicks = None
#        dispatch.id.instLanguage.langList = None
#        dispatch.id.instLanguage.allSupportedLangs = None
#        dispatch.intf.icw.buff = None
#    except:
#        pass
    
    try:
        out.write("\n\n")
        dumpClass(dispatch, out)
    except:
        out.write("\nException occurred during state dump:\n")
        traceback.print_exc(None, out)

    for file in ("/tmp/syslog", "/tmp/anaconda.log", "/tmp/netinfo",
                 "/tmp/lvmout",
                 dispatch.instPath + "/root/install.log",
                 dispatch.instPath + "/root/upgrade.log"):
        try:
            f = open(file, 'r')
            line = "\n\n%s:\n" % (file,)
            while line:
                out.write(line)
                line = f.readline()
            f.close()
        except IOError:
            pass
        except:
            out.write("\nException occurred during %s file copy:\n" % (file,))
            traceback.print_exc(None, out)

def handleException(dispatch, intf, (type, value, tb)):
    # restore original exception handler
    sys.excepthook = sys.__excepthook__

    # get traceback information
    list = traceback.format_exception (type, value, tb)
    text = joinfields (list, "")

    # save to local storage first
    out = open("/tmp/anacdump.txt", "w")
    dumpException (out, text, tb, dispatch)
    out.close()

    # see if /mnt/sysimage is present and put exception there as well
    if os.access("/mnt/sysimage/root", os.X_OK):
        try:
            iutil.copyFile("/tmp/anacdump.txt", "/mnt/sysimage/root/anacdump.txt")
        except:
	    log("Failed to copy anacdump.txt to /mnt/sysimage/root")
            pass
	
    # run kickstart traceback scripts (if necessary)
    try:
	if dispatch.id.instClass.name and dispatch.id.instClass.name == "kickstart":
	    dispatch.id.instClass.runTracebackScripts()
    except:
	pass

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

    # in test mode have save to floppy option just copy to new name
    if not flags.setupFilesystems:
        try:
            iutil.copyFile("/tmp/anacdump.txt", "/tmp/test-anacdump.txt")
        except:
	    log("Failed to copy anacdump.txt to /tmp/test-anacdump.txt")
            pass

        intf.__del__ ()
        os.kill(os.getpid(), signal.SIGKILL)

    while 1:
	rc = intf.dumpWindow()
	if rc:
	    intf.__del__ ()
            os.kill(os.getpid(), signal.SIGKILL)

	device = dispatch.id.floppyDevice
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

	# copy trace dump we wrote to local storage to floppy
        try:
            iutil.copyFile("/tmp/anacdump.txt", "/tmp/crash/anacdump.txt")
        except:
	    log("Failed to copy anacdump.txt to floppy")
            pass

	isys.umount("/tmp/crash")

	intf.messageWindow(_("Dump Written"),
	    _("Your system's state has been successfully written to the "
	      "floppy. Your system will now be reset."))

	intf.__del__ ()
        os.kill(os.getpid(), signal.SIGKILL)
