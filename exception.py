#
# exception.py - general exception formatting and saving
#
# Copyright (C) 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007  Red Hat, Inc.
# All rights reserved.
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
# Author(s): Matt Wilson <msw@redhat.com>
#            Erik Troan <ewt@redhat.com>
#            Chris Lumens <clumens@redhat.com>
#

from constants import *
import isys
import sys
import os
import shutil
import signal
import traceback
import iutil
import types
import bdb
import partedUtils
from string import joinfields
from cPickle import Pickler
from flags import flags
import kickstart

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")

dumpHash = {}

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
                    s = str(item)
                    fd.write("%s" % s[:1024])
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
                    s = str(v)
                    fd.write("%s" % s[:1024])
            fd.write("}\n")
        elif type(value) == types.InstanceType:
            fd.write("%s%s: " % (pad, curkey))
            dumpClass(value, fd, level + 1, parentkey=curkey, skipList=skipList)
        else:
            s = str(value)
            fd.write("%s%s: %s\n" % (pad, curkey, s[:1024]))

def dumpException(out, text, tb, anaconda):
    skipList = [ "anaconda.backend.ayum",
                 "anaconda.backend.dlpkgs",
                 "anaconda.id.accounts",
                 "anaconda.id.bootloader.password",
                 "anaconda.id.comps",
                 "anaconda.id.dispatch",
                 "anaconda.id.hdList",
                 "anaconda.id.ksdata.bootloader",
                 "anaconda.id.ksdata.rootpw",
                 "anaconda.id.ksdata.vnc",
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
                 "anaconda.intf.icw.buff",
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
                 "/tmp/lvmout", "/tmp/resize.out",
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

# Save the traceback to a remote system via SCP.  Returns success or not.
def copyExceptionToRemote(intf, scpInfo):
    import pty

    (host, path, user, password) = scpInfo

    if host.find(":") != -1:
        (host, port) = host.split(":")

        # Try to convert the port to an integer just as a check to see
        # if it's a valid port number.  If not, they'll get a chance to
        # correct the information when scp fails.
        try:
            int(port)
            portArgs = ["-P", port]
        except ValueError:
            portArgs = []
    else:
        portArgs = []

    # Thanks to Will Woods <wwoods@redhat.com> for the scp control
    # here and in scpAuthenticate.

    # Fork ssh into its own pty
    (childpid, master) = pty.fork()
    if childpid < 0:
        log.critical("Could not fork process to run scp")
        return False
    elif childpid == 0:
        # child process - run scp
        args = ["scp", "-oNumberOfPasswordPrompts=1",
                "-oStrictHostKeyChecking=no"] + portArgs + \
               ["/tmp/anacdump.txt", "%s@%s:%s" % (user, host, path)]
        os.execvp("scp", args)

    # parent process
    try:
        childstatus = scpAuthenticate(master, childpid, password)
    except OSError:
        return False

    os.close(master)

    if os.WIFEXITED(childstatus) and os.WEXITSTATUS(childstatus) == 0:
        return True
    else:
        return False

# Save the traceback to a removable storage device, such as a floppy disk
# or a usb/firewire drive.  If there's no filesystem on the disk/partition,
# write a vfat one.
# Returns success or not.
def copyExceptionToDisk(anaconda, device):
    # in test mode have save to disk option just copy to new name
    if not flags.setupFilesystems:
        try:
            shutil.copyfile("/tmp/anacdump.txt", "/tmp/test-anacdump.txt")
        except:
            log.error("Failed to copy anacdump.txt to /tmp/test-anacdump.txt")
            pass

        anaconda.intf.__del__ ()
        return True

    try:
        fd = os.open(device, os.O_RDONLY)
    except:
        return False

    os.close(fd)

    fstype = partedUtils.sniffFilesystemType(device)
    if fstype == None:
        fstype = 'vfat'
    try:
        isys.mount(device, "/tmp/crash", fstype)
    except SystemError:
        if fstype != 'vfat':
            return False
        cmd = "/usr/sbin/mkdosfs"

        if os.access("/sbin/mkdosfs", os.X_OK):
            cmd = "/sbin/mkdosfs"

        iutil.execWithRedirect (cmd, [device], stdout = '/dev/tty5',
                                stderr = '/dev/tty5')

        try:
            isys.mount(device, "/tmp/crash", fstype)
        except SystemError:
            return False

    # copy trace dump we wrote to local storage to disk
    try:
        shutil.copyfile("/tmp/anacdump.txt", "/tmp/crash/anacdump.txt")
    except:
        log.error("Failed to copy anacdump.txt to device %s" % device)
        return False

    isys.umount("/tmp/crash")
    return True

# Reverse the order that tracebacks are printed so people will hopefully quit
# giving us the least useful part of the exception in bug reports.
def formatException (type, value, tb):
    lst = traceback.format_tb(tb)
    lst.reverse()
    lst.insert(0, "anaconda %s exception report\n" % os.getenv("ANACONDAVERSION"))
    lst.insert(1, 'Traceback (most recent call first):\n')
    lst.extend(traceback.format_exception_only(type, value))
    return lst

def runSaveDialog(anaconda, longTracebackFile):
    saveWin = anaconda.intf.saveExceptionWindow(anaconda, longTracebackFile)
    if not saveWin:
        anaconda.intf.__del__()
        os.kill(os.getpid(), signal.SIGKILL)

    while 1:
        saveWin.run()
        rc = saveWin.getrc()

        if rc == EXN_OK:
            if saveWin.saveToDisk():
                device = saveWin.getDest()
                cpSucceeded = copyExceptionToDisk(anaconda, device)

                if cpSucceeded:
                    anaconda.intf.messageWindow(_("Dump Written"),
                        _("Your system's state has been successfully written to "
                          "the disk. The installer will now exit."),
                        type="custom", custom_icon="info",
                        custom_buttons=[_("_Exit installer")])
                    sys.exit(0)
                else:
                    anaconda.intf.messageWindow(_("Dump Not Written"),
                        _("There was a problem writing the system state to the "
                          "disk."))
                    continue
            elif saveWin.saveToLocal():
                dest = saveWin.getDest()
                try:
                    shutil.copyfile("/tmp/anacdump.txt", "%s/InstallError.txt" %(dest,))
                    anaconda.intf.messageWindow(_("Dump Written"),
                        _("Your system's state has been successfully written to "
                          "the disk. The installer will now exit."),
                        type="custom", custom_icon="info",
                        custom_buttons=[_("_Exit installer")])
                    sys.exit(0)
                except Exception, e:
                    log.error("Failed to copy anacdump.txt to %s/anacdump.txt: %s" %(dest, e))
                else:
                    anaconda.intf.messageWindow(_("Dump Not Written"),
                        _("There was a problem writing the system state to the "
                          "disk."))
                    continue
            else:
                if not network.hasActiveNetDev() and not anaconda.intf.enableNetwork(anaconda):
                    scpSucceeded = False
                else:
                    scpInfo = saveWin.getDest()
                    scpSucceeded = copyExceptionToRemote(anaconda.intf, scpInfo)

                if scpSucceeded:
                    anaconda.intf.messageWindow(_("Dump Written"),
                        _("Your system's state has been successfully written to "
                          "the remote host.  The installer will now exit."),
                        type="custom", custom_icon="info",
                        custom_buttons=[_("_Exit installer")])
                    sys.exit(0)
                else:
                    anaconda.intf.messageWindow(_("Dump Not Written"),
                        _("There was a problem writing the system state to the "
                          "remote host."))
                    continue
        elif rc == EXN_CANCEL:
            break

    saveWin.pop()

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
            kickstart.runTracebackScripts(anaconda)
    except:
        pass

    mainWin = anaconda.intf.mainExceptionWindow(text, "/tmp/anacdump.txt")
    if not mainWin:
        anaconda.intf.__del__()
        os.kill(os.getpid(), signal.SIGKILL)

    while 1:
        mainWin.run()
        rc = mainWin.getrc()

        if rc == EXN_OK:
            anaconda.intf.__del__ ()
            os.kill(os.getpid(), signal.SIGKILL)
        elif rc == EXN_DEBUG:
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
        elif rc == EXN_SAVE:
            runSaveDialog(anaconda, "/tmp/anacdump.txt")
