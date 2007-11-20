#
# exception.py - general exception formatting and saving
#
# Matt Wilson <msw@redhat.com>
# Erik Troan <ewt@redhat.com>
#
# Copyright 2000-2005 Red Hat, Inc.
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
import shutil
import signal
import traceback
import iutil
import types
import rpm
import bdb
import rhpl
import time
from string import joinfields
from cPickle import Pickler
from rhpl.translate import _
from flags import flags

import logging
log = logging.getLogger("anaconda")

dumpHash = {}

# XXX do length limits on obj dumps.
def dumpClass(instance, fd, level=0, parentkey="", skipList=[]):
    # protect from loops
    try:
        if not dumpHash.has_key(instance):
            dumpHash[instance] = None
        else:
            fd.write("Already dumped\n")
            return
    except TypeError:
        fd.write("Cannot dump object\n")
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

        # Don't dump objects that are in our skip list, though ones that are
        # None are probably okay.
	if eval("instance.%s is not None" % key) and \
           eval("id(instance.%s)" % key) in skipList:
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
                    dumpClass(item, fd, level + 1, skipList=skipList)
                else:
                    fd.write("%s" % (item,))
            fd.write("]\n")
        elif type(value) == types.DictType:
            fd.write("%s%s: {" % (pad, curkey))
            first = 1
            for k, v in value.items():
                if not first:
                    fd.write(", ")
                else:
                    first = 0
                if type(k) == types.StringType:
                    fd.write("'%s': " % (k,))
                else:
                    fd.write("%s: " % (k,))
                if type(v) == types.InstanceType:
                    dumpClass(v, fd, level + 1, parentkey = curkey, skipList=skipList)
                else:
                    fd.write("%s" % (v,))
            fd.write("}\n")
        elif type(value) == types.InstanceType:
            fd.write("%s%s: " % (pad, curkey))
            dumpClass(value, fd, level + 1, parentkey=curkey, skipList=skipList)
        else:
            fd.write("%s%s: %s\n" % (pad, curkey, value))

def dumpException(out, text, tb, anaconda):
    skipList = [ "anaconda.backend.ayum",
                 "anaconda.backend.dlpkgs",
                 "anaconda.id.accounts",
                 "anaconda.id.bootloader.password",
                 "anaconda.id.comps",
                 "anaconda.id.dispatch",
                 "anaconda.id.hdList",
                 "anaconda.id.instClass.handlers.handlers",
                 "anaconda.id.instClass.ksparser.handler",
                 "anaconda.id.instClass.ksparser.handler.ksdata.bootloader",
                 "anaconda.id.instClass.ksparser.handler.ksdata.rootpw",
                 "anaconda.id.instClass.ksparser.handler.ksdata.vnc",
                 "anaconda.id.instLanguage.font",
                 "anaconda.id.instLanguage.kbd",
                 "anaconda.id.instLanguage.info",
                 "anaconda.id.instLanguage.localeInfo",
                 "anaconda.id.instLanguage.nativeLangNames",
                 "anaconda.id.instLanguage.tz",
                 "anaconda.id.keyboard._mods._modelDict",
                 "anaconda.id.keyboard.modelDict",
                 "anaconda.id.rootPassword",
                 "anaconda.id.tmpData",
                 "anaconda.id.xsetup.xserver.hwstate.monitor.monlist",
                 "anaconda.id.xsetup.xserver.hwstate.monitor.monids",
                 "anaconda.intf.icw.buff",
                 "anaconda.intf.icw.releaseNotesContents",
                 "anaconda.intf.icw.stockButtons",
                 "dispatch.sack.excludes",
               ]
    idSkipList = []

    # Catch attributes that do not exist at the time we do the exception dump
    # and ignore them.
    for k in skipList:
        try:
            eval("idSkipList.append(id(%s))" % k)
        except:
            pass

    p = Pickler(out)

    out.write(text)

    trace = tb
    if trace is not None:
        while trace.tb_next:
            trace = trace.tb_next
        frame = trace.tb_frame
        out.write ("\nLocal variables in innermost frame:\n")
        try:
            for (key, value) in frame.f_locals.items():
                out.write ("%s: %s\n" % (key, value))
        except:
            pass

    try:
        out.write("\n\n")
        dumpClass(anaconda, out, skipList=idSkipList)
    except:
        out.write("\nException occurred during state dump:\n")
        traceback.print_exc(None, out)

    for file in ("/tmp/syslog", "/tmp/anaconda.log", "/tmp/netinfo",
                 "/tmp/lvmout",
                 anaconda.rootPath + "/root/install.log",
                 anaconda.rootPath + "/root/upgrade.log"):
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

def scpAuthenticate(master, childpid, password):
    while 1:
        # Read up to password prompt.  Propagate OSError exceptions, which
        # can occur for anything that causes scp to immediately die (bad
        # hostname, host down, etc.)
        buf = os.read(master, 4096)
        if buf.lower().find("password: ") != -1:
            os.write(master, password+"\n")
            # read the space and newline that get echoed back
            os.read(master, 2)
            break

    while 1:
        buf = ""
        try:
            buf = os.read(master, 4096)
        except (OSError, EOFError):
            break

    (pid, childstatus) = os.waitpid (childpid, 0)
    return childstatus

# Returns 0 on success, 1 on cancel, 2 on error.
def copyExceptionToRemote(intf):
    import pty

    scpWin = intf.scpWindow()
    while 1:
        # Bail if they hit the cancel button.
        scpWin.run()
        scpInfo = scpWin.getrc()

        if scpInfo == None:
            scpWin.pop()
            return 1

        (host, path, user, password) = scpInfo

        # Thanks to Will Woods <wwoods@redhat.com> for the scp control
        # here and in scpAuthenticate.

        # Fork ssh into its own pty
        (childpid, master) = pty.fork()
        if childpid < 0:
            log.critical("Could not fork process to run scp")
            scpWin.pop()
            return 2
        elif childpid == 0:
            # child process - run scp
            args = ["scp", "-oNumberOfPasswordPrompts=1",
                    "-oStrictHostKeyChecking=no", "/tmp/anacdump.txt",
                    "%s@%s:%s" % (user, host, path)]
            os.execvp("scp", args)

        # parent process
        try:
            childstatus = scpAuthenticate(master, childpid, password)
        except OSError:
            scpWin.pop()
            return 2

        os.close(master)

        if os.WIFEXITED(childstatus) and os.WEXITSTATUS(childstatus) == 0:
            return 0
        else:
            scpWin.pop()
            return 2

def copyExceptionToFloppy (anaconda):
    # in test mode have save to floppy option just copy to new name
    if not flags.setupFilesystems:
        try:
            shutil.copyfile("/tmp/anacdump.txt", "/tmp/test-anacdump.txt")
        except:
            log.error("Failed to copy anacdump.txt to /tmp/test-anacdump.txt")
            pass

        anaconda.intf.__del__ ()
        return 2

    while 1:
        # Bail if they hit the cancel button.
        rc = anaconda.intf.dumpWindow()
        if rc:
            return 1

        device = anaconda.id.floppyDevice
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

        if rhpl.getArch() != "ia64":
            cmd = "/usr/sbin/mkdosfs"

            if os.access("/sbin/mkdosfs", os.X_OK):
                cmd = "/sbin/mkdosfs"

            iutil.execWithRedirect (cmd, ["/tmp/floppy"], stdout = '/dev/tty5',
                                    stderr = '/dev/tty5')

        try:
            isys.mount(device, "/tmp/crash", fstype = "vfat")
        except SystemError:
            continue

        # copy trace dump we wrote to local storage to floppy
        try:
            shutil.copyfile("/tmp/anacdump.txt", "/tmp/crash/anacdump.txt")
        except:
            log.error("Failed to copy anacdump.txt to floppy")
            return 2

        isys.umount("/tmp/crash")
        return 0

# Reverse the order that tracebacks are printed so people will hopefully quit
# giving us the least useful part of the exception in bug reports.
def formatException (type, value, tb):
    lst = traceback.format_tb(tb)
    lst.reverse()
    lst.insert(0, 'Traceback (most recent call first):\n')
    lst.extend(traceback.format_exception_only(type, value))
    return lst

def handleException(anaconda, (type, value, tb)):
    if isinstance(value, bdb.BdbQuit):
        sys.exit(1)
        
    # restore original exception handler
    sys.excepthook = sys.__excepthook__

    # get traceback information
    list = formatException (type, value, tb)
    text = joinfields (list, "")

    # save to local storage first
    out = open("/tmp/anacdump.txt", "w")
    dumpException (out, text, tb, anaconda)
    out.close()

    # see if /mnt/sysimage is present and put exception there as well
    if os.access("/mnt/sysimage/root", os.X_OK):
        try:
            shutil.copyfile("/tmp/anacdump.txt", "/mnt/sysimage/root/anacdump.txt")
        except:
            log.error("Failed to copy anacdump.txt to /mnt/sysimage/root")
            pass

    # run kickstart traceback scripts (if necessary)
    try:
        if anaconda.isKickstart:
            anaconda.id.instClass.runTracebackScripts()
    except:
        pass

    win = anaconda.intf.exceptionWindow(text, "/tmp/anacdump.txt")
    if not win:
        anaconda.intf.__del__()
        os.kill(os.getpid(), signal.SIGKILL)

    while 1:
        win.run()
        rc = win.getrc()

        if rc == 0:
            anaconda.intf.__del__ ()
            os.kill(os.getpid(), signal.SIGKILL)
        elif rc == 1:
            anaconda.intf.__del__ ()
            print text

            pidfl = "/tmp/vncshell.pid"
            if os.path.exists(pidfl) and os.path.isfile(pidfl):
                pf = open(pidfl, "r")
                for pid in pf.readlines():
                    if not int(pid) == os.getpid():
                        os.kill(int(pid), signal.SIGKILL)
                pf.close()

            if not flags.test:
                os.open("/dev/console", os.O_RDWR)   # reclaim stdin
                os.dup2(0, 1)                        # reclaim stdout
                os.dup2(0, 2)                        # reclaim stderr
                #   ^
                #   |
                #   +------ dup2 is magic, I tells ya!

            # bring back the echo
            import termios
            si = sys.stdin.fileno()
            attr = termios.tcgetattr(si)
            attr[3] = attr[3] & termios.ECHO
            termios.tcsetattr(si, termios.TCSADRAIN, attr)

            print "\nEntering debugger..."
            import pdb
            pdb.post_mortem (tb)
            os.kill(os.getpid(), signal.SIGKILL)
        elif rc == 2:
            floppyRc = copyExceptionToFloppy(anaconda)

            if floppyRc == 0:
                anaconda.intf.messageWindow(_("Dump Written"),
                    _("Your system's state has been successfully written to "
                      "the floppy. Your system will now be rebooted."),
                    type="custom", custom_icon="info",
                    custom_buttons=[_("_Reboot")])
                sys.exit(0)
            elif floppyRc == 1:
                continue
            elif floppyRc == 2:
                anaconda.intf.messageWindow(_("Dump Not Written"),
                    _("There was a problem writing the system state to the "
                      "floppy."))
                continue
        elif rc == 3:
            scpRc = copyExceptionToRemote(anaconda.intf)

            if scpRc == 0:
                anaconda.intf.messageWindow(_("Dump Written"),
                    _("Your system's state has been successfully written to "
                      "the remote host.  Your system will now be rebooted."),
                    type="custom", custom_icon="info",
                    custom_buttons=[_("_Reboot")])
                sys.exit(0)
            elif scpRc == 1:
                continue
            elif scpRc == 2:
                anaconda.intf.messageWindow(_("Dump Not Written"),
                    _("There was a problem writing the system state to the "
                      "remote host."))
                continue
