#
# iutil.py - generic install utility functions
#
# Copyright (C) 1999, 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007
# Red Hat, Inc.  All rights reserved.
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
# Author(s): Erik Troan <ewt@redhat.com>
#

import glob
import os, string, stat, sys
import signal
import os.path
from errno import *
import warnings
import subprocess
from flags import flags
from constants import *
import re
import threading

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")
program_log = logging.getLogger("program")

#Python reimplementation of the shell tee process, so we can
#feed the pipe output into two places at the same time
class tee(threading.Thread):
    def __init__(self, inputdesc, outputdesc, logmethod):
        threading.Thread.__init__(self)
        self.inputdesc = os.fdopen(inputdesc, "r")
        self.outputdesc = outputdesc
        self.logmethod = logmethod
        self.running = True

    def run(self):
        while self.running:
            data = self.inputdesc.readline()
            if data == "":
                self.running = False
            else:
                self.logmethod(data.rstrip('\n'))
                os.write(self.outputdesc, data)

    def stop(self):
        self.running = False
        return self

## Run an external program and redirect the output to a file.
# @param command The command to run.
# @param argv A list of arguments.
# @param stdin The file descriptor to read stdin from.
# @param stdout The file descriptor to redirect stdout to.
# @param stderr The file descriptor to redirect stderr to.
# @param root The directory to chroot to before running command.
# @return The return code of command.
def execWithRedirect(command, argv, stdin = None, stdout = None,
                     stderr = None, root = '/'):
    def chroot ():
        os.chroot(root)

    stdinclose = stdoutclose = stderrclose = lambda : None

    argv = list(argv)
    if isinstance(stdin, str):
        if os.access(stdin, os.R_OK):
            stdin = os.open(stdin, os.O_RDONLY)
            stdinclose = lambda : os.close(stdin)
        else:
            stdin = sys.stdin.fileno()
    elif isinstance(stdin, int):
        pass
    elif stdin is None or not isinstance(stdin, file):
        stdin = sys.stdin.fileno()

    if isinstance(stdout, str):
        stdout = os.open(stdout, os.O_RDWR|os.O_CREAT)
        stdoutclose = lambda : os.close(stdout)
    elif isinstance(stdout, int):
        pass
    elif stdout is None or not isinstance(stdout, file):
        stdout = sys.stdout.fileno()

    if isinstance(stderr, str):
        stderr = os.open(stderr, os.O_RDWR|os.O_CREAT)
        stderrclose = lambda : os.close(stderr)
    elif isinstance(stderr, int):
        pass
    elif stderr is None or not isinstance(stderr, file):
        stderr = sys.stderr.fileno()

    program_log.info("Running... %s" % (" ".join([command] + argv),))

    #prepare os pipes for feeding tee proceses
    pstdout, pstdin = os.pipe()
    perrout, perrin = os.pipe()
   
    env = os.environ.copy()
    env.update({"LC_ALL": "C"})

    try:
        #prepare tee proceses
        proc_std = tee(pstdout, stdout, program_log.info)
        proc_err = tee(perrout, stderr, program_log.error)

        #start monitoring the outputs
        proc_std.start()
        proc_err.start()

        proc = subprocess.Popen([command] + argv, stdin=stdin,
                                stdout=pstdin,
                                stderr=perrin,
                                preexec_fn=chroot, cwd=root,
                                env=env)

        proc.wait()
        ret = proc.returncode

        #close the input ends of pipes so we get EOF in the tee processes
        os.close(pstdin)
        os.close(perrin)

        #wait for the output to be written and destroy them
        proc_std.join()
        del proc_std

        proc_err.join()
        del proc_err

        stdinclose()
        stdoutclose()
        stderrclose()
    except OSError as e:
        errstr = "Error running %s: %s" % (command, e.strerror)
        log.error(errstr)
        program_log.error(errstr)
        #close the input ends of pipes so we get EOF in the tee processes
        os.close(pstdin)
        os.close(perrin)
        proc_std.join()
        proc_err.join()

        stdinclose()
        stdoutclose()
        stderrclose()
        raise RuntimeError, errstr

    return ret

## Run an external program and capture standard out.
# @param command The command to run.
# @param argv A list of arguments.
# @param stdin The file descriptor to read stdin from.
# @param stderr The file descriptor to redirect stderr to.
# @param root The directory to chroot to before running command.
# @return The output of command from stdout.
def execWithCapture(command, argv, stdin = None, stderr = None, root='/'):
    def chroot():
        os.chroot(root)

    def closefds ():
        stdinclose()
        stderrclose()

    stdinclose = stderrclose = lambda : None
    rc = ""
    argv = list(argv)

    if isinstance(stdin, str):
        if os.access(stdin, os.R_OK):
            stdin = os.open(stdin, os.O_RDONLY)
            stdinclose = lambda : os.close(stdin)
        else:
            stdin = sys.stdin.fileno()
    elif isinstance(stdin, int):
        pass
    elif stdin is None or not isinstance(stdin, file):
        stdin = sys.stdin.fileno()

    if isinstance(stderr, str):
        stderr = os.open(stderr, os.O_RDWR|os.O_CREAT)
        stderrclose = lambda : os.close(stderr)
    elif isinstance(stderr, int):
        pass
    elif stderr is None or not isinstance(stderr, file):
        stderr = sys.stderr.fileno()

    program_log.info("Running... %s" % (" ".join([command] + argv),))

    env = os.environ.copy()
    env.update({"LC_ALL": "C"})

    try:
        proc = subprocess.Popen([command] + argv, stdin=stdin,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                preexec_fn=chroot, cwd=root,
                                env=env)

        while True:
            (outStr, errStr) = proc.communicate()
            if outStr:
                map(program_log.info, outStr.splitlines())
                rc += outStr
            if errStr:
                map(program_log.error, errStr.splitlines())
                os.write(stderr, errStr)

            if proc.returncode is not None:
                break
    except OSError as e:
        log.error ("Error running " + command + ": " + e.strerror)
        closefds()
        raise RuntimeError, "Error running " + command + ": " + e.strerror

    closefds()
    return rc

def execWithCallback(command, argv, stdin = None, stdout = None,
                     stderr = None, echo = True, callback = None,
                     callback_data = None, root = '/'):
    def chroot():
        os.chroot(root)

    def closefds ():
        stdinclose()
        stdoutclose()
        stderrclose()

    stdinclose = stdoutclose = stderrclose = lambda : None

    argv = list(argv)
    if isinstance(stdin, str):
        if os.access(stdin, os.R_OK):
            stdin = os.open(stdin, os.O_RDONLY)
            stdinclose = lambda : os.close(stdin)
        else:
            stdin = sys.stdin.fileno()
    elif isinstance(stdin, int):
        pass
    elif stdin is None or not isinstance(stdin, file):
        stdin = sys.stdin.fileno()

    if isinstance(stdout, str):
        stdout = os.open(stdout, os.O_RDWR|os.O_CREAT)
        stdoutclose = lambda : os.close(stdout)
    elif isinstance(stdout, int):
        pass
    elif stdout is None or not isinstance(stdout, file):
        stdout = sys.stdout.fileno()

    if isinstance(stderr, str):
        stderr = os.open(stderr, os.O_RDWR|os.O_CREAT)
        stderrclose = lambda : os.close(stderr)
    elif isinstance(stderr, int):
        pass
    elif stderr is None or not isinstance(stderr, file):
        stderr = sys.stderr.fileno()

    program_log.info("Running... %s" % (" ".join([command] + argv),))

    p = os.pipe()
    p_stderr = os.pipe()
    childpid = os.fork()
    if not childpid:
        os.close(p[0])
        os.close(p_stderr[0])
        os.dup2(p[1], 1)
        os.dup2(p_stderr[1], 2)
        os.dup2(stdin, 0)
        os.close(stdin)
        os.close(p[1])
        os.close(p_stderr[1])

        os.execvp(command, [command] + argv)
        os._exit(1)

    os.close(p[1])
    os.close(p_stderr[1])

    logline = ''
    while 1:
        try:
            s = os.read(p[0], 1)
        except OSError as e:
            if e.errno != 4:
                raise IOError, e.args

        if echo:
            os.write(stdout, s)

        if s == '\n':
            program_log.info(logline)
            logline = ''
        else:
            logline += s

        if callback:
            callback(s, callback_data=callback_data)

        # break out early if the sub-process changes status.
        # no need to flush the stream if the process has exited
        try:
            (pid, status) = os.waitpid(childpid,os.WNOHANG)
            if pid != 0:
                break
        except OSError as e:
            log.critical("exception from waitpid: %s %s" %(e.errno, e.strerror))

        if len(s) < 1:
            break
    if len(logline) > 0:
        program_log.info(logline)

    log_errors = ''
    while 1:
        try:
            err = os.read(p_stderr[0], 128)
        except OSError as e:
            if e.errno != 4:
                raise IOError, e.args
            break
        log_errors += err
        if len(err) < 1:
            break
    map(program_log.error, log_errors.splitlines())
    os.close(p[0])
    os.close(p_stderr[0])

    try:
        #if we didn't already get our child's exit status above, do so now.
        if not pid:
            (pid, status) = os.waitpid(childpid, 0)
    except OSError as e:
        log.critical("exception from waitpid: %s %s" %(e.errno, e.strerror))

    closefds()
    # *shrug*  no clue why this would happen, but hope that things are fine
    if status is None:
        return 0

    if os.WIFEXITED(status):
        return os.WEXITSTATUS(status)

    return 1

def _pulseProgressCallback(data, callback_data=None):
    if callback_data:
        callback_data.pulse()

def execWithPulseProgress(command, argv, stdin = None, stdout = None,
                          stderr = None, echo = True, progress = None,
                          root = '/'):
    return execWithCallback(command, argv, stdin=stdin, stdout=stdout,
                     stderr=stderr, echo=echo, callback=_pulseProgressCallback,
                     callback_data=progress, root=root)

## Run a shell.
def execConsole():
    try:
        proc = subprocess.Popen(["/bin/sh"])
        proc.wait()
    except OSError as e:
        raise RuntimeError, "Error running /bin/sh: " + e.strerror

## Get the size of a directory and all its subdirectories.
# @param dir The name of the directory to find the size of.
# @return The size of the directory in kilobytes.
def getDirSize(dir):
    def getSubdirSize(dir):
	# returns size in bytes
        mydev = os.lstat(dir)[stat.ST_DEV]

        dsize = 0
        for f in os.listdir(dir):
	    curpath = '%s/%s' % (dir, f)
	    sinfo = os.lstat(curpath)
            if stat.S_ISDIR(sinfo[stat.ST_MODE]):
                if mydev == sinfo[stat.ST_DEV]:
                    dsize += getSubdirSize(curpath)
            elif stat.S_ISREG(sinfo[stat.ST_MODE]):
                dsize += sinfo[stat.ST_SIZE]
            else:
                pass

        return dsize
    return getSubdirSize(dir)/1024

## Get the amount of RAM not used by /tmp.
# @return The amount of available memory in kilobytes.
def memAvailable():
    tram = memInstalled()

    ramused = getDirSize("/tmp")
    return tram - ramused

## Get the amount of RAM installed in the machine.
# @return The amount of installed memory in kilobytes.
def memInstalled():
    f = open("/proc/meminfo", "r")
    lines = f.readlines()
    f.close()

    for l in lines:
        if l.startswith("MemTotal:"):
            fields = string.split(l)
            mem = fields[1]
            break

    return int(mem)

## Suggest the size of the swap partition that will be created.
# @param quiet Should size information be logged?
# @return A tuple of the minimum and maximum swap size, in megabytes.
def swapSuggestion(quiet=0):
    mem = memInstalled()/1024
    mem = ((mem/16)+1)*16
    if not quiet:
	log.info("Detected %sM of memory", mem)
	
    if mem <= 256:
        minswap = 256
        maxswap = 512
    else:
        if mem > 2048:
            minswap = 1024
            maxswap = 2048 + mem
        else:
            minswap = mem
            maxswap = 2*mem

    if not quiet:
	log.info("Swap attempt of %sM to %sM", minswap, maxswap)

    return (minswap, maxswap)

## Create a directory path.  Don't fail if the directory already exists.
# @param dir The directory path to create.
def mkdirChain(dir):
    try:
        os.makedirs(dir, 0755)
    except OSError as e:
        try:
            if e.errno == EEXIST and stat.S_ISDIR(os.stat(dir).st_mode):
                return
        except:
            pass

        log.error("could not create directory %s: %s" % (dir, e.strerror))

## Get the total amount of swap memory.
# @return The total amount of swap memory in kilobytes, or 0 if unknown.
def swapAmount():
    f = open("/proc/meminfo", "r")
    lines = f.readlines()
    f.close()

    for l in lines:
        if l.startswith("SwapTotal:"):
            fields = string.split(l)
            return int(fields[1])
    return 0

## Copy a device node.
# Copies a device node by looking at the device type, major and minor device
# numbers, and doing a mknod on the new device name.
#
# @param src The name of the source device node.
# @param dest The name of the new device node to create.
def copyDeviceNode(src, dest):
    filestat = os.lstat(src)
    mode = filestat[stat.ST_MODE]
    if stat.S_ISBLK(mode):
        type = stat.S_IFBLK
    elif stat.S_ISCHR(mode):
        type = stat.S_IFCHR
    else:
        # XXX should we just fallback to copying normally?
        raise RuntimeError, "Tried to copy %s which isn't a device node" % (src,)

    os.mknod(dest, mode | type, filestat.st_rdev)

## Get the PPC machine variety type.
# @return The PPC machine type, or 0 if not PPC.
def getPPCMachine():
    if not isPPC():
        return 0

    ppcMachine = None
    machine = None
    platform = None

    # ppc machine hash
    ppcType = { 'Mac'      : 'PMac',
                'Book'     : 'PMac',
                'CHRP IBM' : 'pSeries',
                'Pegasos'  : 'Pegasos',
                'Efika'    : 'Efika',
                'iSeries'  : 'iSeries',
                'pSeries'  : 'pSeries',
                'PReP'     : 'PReP',
                'CHRP'     : 'pSeries',
                'Amiga'    : 'APUS',
                'Gemini'   : 'Gemini',
                'Shiner'   : 'ANS',
                'BRIQ'     : 'BRIQ',
                'Teron'    : 'Teron',
                'AmigaOne' : 'Teron',
                'Maple'    : 'pSeries',
                'Cell'     : 'pSeries',
                'Momentum' : 'pSeries',
                'PS3'      : 'PS3'
                }

    f = open('/proc/cpuinfo', 'r')
    lines = f.readlines()
    f.close()
    for line in lines:
        if line.find('machine') != -1:
            machine = line.split(':')[1]
        elif line.find('platform') != -1:
            platform = line.split(':')[1]

    for part in (machine, platform):
        if ppcMachine is None and part is not None:
            for type in ppcType.items():
                if part.find(type[0]) != -1:
                    ppcMachine = type[1]

    if ppcMachine is None:
        log.warning("Unable to find PowerPC machine type")
    elif ppcMachine == 0:
        log.warning("Unknown PowerPC machine type: %s" %(ppcMachine,))

    return ppcMachine

## Get the powermac machine ID.
# @return The powermac machine id, or 0 if not PPC.
def getPPCMacID():
    machine = None

    if not isPPC():
        return 0
    if getPPCMachine() != "PMac":
        return 0

    f = open('/proc/cpuinfo', 'r')
    lines = f.readlines()
    f.close()
    for line in lines:
      if line.find('machine') != -1:
        machine = line.split(':')[1]
        machine = machine.strip()
        return machine

    log.warning("No Power Mac machine id")
    return 0

## Get the powermac generation.
# @return The powermac generation, or 0 if not powermac.
def getPPCMacGen():
    # XXX: should NuBus be here?
    pmacGen = ['OldWorld', 'NewWorld', 'NuBus']

    if not isPPC():
        return 0
    if getPPCMachine() != "PMac":
        return 0

    f = open('/proc/cpuinfo', 'r')
    lines = f.readlines()
    f.close()
    gen = None
    for line in lines:
      if line.find('pmac-generation') != -1:
        gen = line.split(':')[1]
        break

    if gen is None:
        log.warning("Unable to find pmac-generation")

    for type in pmacGen:
      if gen.find(type) != -1:
          return type

    log.warning("Unknown Power Mac generation: %s" %(gen,))
    return 0

## Determine if the hardware is an iBook or PowerBook
# @return 1 if so, 0 otherwise.
def getPPCMacBook():
    if not isPPC():
        return 0
    if getPPCMachine() != "PMac":
        return 0

    f = open('/proc/cpuinfo', 'r')
    lines = f.readlines()
    f.close()

    for line in lines:
      if not string.find(string.lower(line), 'book') == -1:
        return 1
    return 0

cell = None
## Determine if the hardware is the Cell platform.
# @return True if so, False otherwise.
def isCell():
    global cell
    if cell is not None:
        return cell

    cell = False
    if not isPPC():
        return cell

    f = open('/proc/cpuinfo', 'r')
    lines = f.readlines()
    f.close()

    for line in lines:
      if not string.find(line, 'Cell') == -1:
          cell = True

    return cell

mactel = None
## Determine if the hardware is an Intel-based Apple Mac.
# @return True if so, False otherwise.
def isMactel():
    global mactel
    if mactel is not None:
        return mactel

    if not isX86():
        mactel = False
    elif not os.path.exists("/usr/sbin/dmidecode"):
        mactel = False
    else:
        buf = execWithCapture("/usr/sbin/dmidecode",
                              ["dmidecode", "-s", "system-manufacturer"])
        if buf.lower().find("apple") != -1:
            mactel = True
        else:
            mactel = False
    return mactel

efi = None
## Determine if the hardware supports EFI.
# @return True if so, False otherwise.
def isEfi():
    global efi
    if efi is not None:
        return efi

    efi = False
    # XXX need to make sure efivars is loaded...
    if os.path.exists("/sys/firmware/efi"):
        efi = True

    return efi

## Generate the /etc/rpm/macros file.
# @param root The root of the filesystem to create the files in.
def writeRpmPlatform(root="/"):
    import rpmUtils.arch

    if os.access("%s/etc/rpm/platform" %(root,), os.R_OK):
        return
    if not os.access("%s/etc/rpm" %(root,), os.X_OK):
        os.mkdir("%s/etc/rpm" %(root,))

    myarch = rpmUtils.arch.canonArch

    # now allow an override with rpmarch=i586 on the command line (#101971)
    if flags.targetarch != None:
        myarch = flags.targetarch

    # now make the current install believe it, too
    rpmUtils.arch.canonArch = myarch

    # FIXME: writing /etc/rpm/macros feels wrong somehow
    # temporary workaround for #92285
    if not (myarch.startswith("ppc64") or
            myarch in ("s390x", "sparc64", "x86_64", "ia64")):
        return
    if os.access("%s/etc/rpm/macros" %(root,), os.R_OK):
        if myarch.startswith("ppc64") or myarch == "sparc64":
            f = open("%s/etc/rpm/macros" %(root,), 'r+')
            lines = f.readlines()
            addPrefer = True
            for line in lines:
                if line.startswith("%_prefer_color"):
                    addPrefer = False
            if addPrefer:    
                f.write("%_prefer_color   1\n")
            f.close()
            return
        else:
            return

    f = open("%s/etc/rpm/macros" %(root,), 'w+')
    f.write("%_transaction_color   3\n")
    if myarch.startswith("ppc64") or myarch == "sparc64":
        f.write("%_prefer_color   1\n")

    f.close()

# Architecture checking functions

def isX86(bits=None):
    arch = os.uname()[4]

    # x86 platforms include:
    #     i*86
    #     athlon*
    #     x86_64
    #     amd*
    #     ia32e
    if bits is None:
        if (arch.startswith('i') and arch.endswith('86')) or \
           arch.startswith('athlon') or arch.startswith('amd') or \
           arch == 'x86_64' or arch == 'ia32e':
            return True
    elif bits == 32:
        if arch.startswith('i') and arch.endswith('86'):
            return True
    elif bits == 64:
        if arch.startswith('athlon') or arch.startswith('amd') or \
           arch == 'x86_64' or arch == 'ia32e':
            return True

    return False

def isPPC():
    return os.uname()[4].startswith('ppc')

def isS390():
    return os.uname()[4].startswith('s390')

def isIA64():
    return os.uname()[4] == 'ia64'

def isAlpha():
    return os.uname()[4].startswith('alpha')

def isSparc():
    return os.uname()[4].startswith('sparc')

def getArch():
    if isX86(bits=32):
        return 'i386'
    elif isX86(bits=64):
        return 'x86_64'
    elif isPPC():
        return 'ppc'
    elif isAlpha():
        return 'alpha'
    elif isSparc():
        return 'sparc'
    else:
        return os.uname()[4]

def isConsoleOnVirtualTerminal():
    # XXX PJFIX is there some way to ask the kernel this instead?
    if isS390():
        return False
    return not flags.serial

def strip_markup(text):
    if text.find("<") == -1:
        return text
    r = ""
    inTag = False
    for c in text:
        if c == ">" and inTag:
            inTag = False
            continue
        elif c == "<" and not inTag:
            inTag = True
            continue
        elif not inTag:
            r += c
    return r.encode("utf-8")

def notify_kernel(path, action="change"):
    """ Signal the kernel that the specified device has changed. """
    log.debug("notifying kernel of '%s' event on device %s" % (action, path))
    path = os.path.join(path, "uevent")
    if not path.startswith("/sys/") or not os.access(path, os.W_OK):
        log.debug("sysfs path '%s' invalid" % path)
        raise ValueError("invalid sysfs path")

    f = open(path, "a")
    f.write("%s\n" % action)
    f.close()

def get_sysfs_path_by_name(dev_name, class_name="block"):
    dev_name = os.path.basename(dev_name)
    sysfs_class_dir = "/sys/class/%s" % class_name
    dev_path = os.path.join(sysfs_class_dir, dev_name)
    if os.path.exists(dev_path):
        return dev_path

def numeric_type(num):
    """ Verify that a value is given as a numeric data type.

        Return the number if the type is sensible or raise ValueError
        if not.
    """
    if num is None:
        num = 0
    elif not (isinstance(num, int) or \
              isinstance(num, long) or \
              isinstance(num, float)):
        raise ValueError("value (%s) must be either a number or None" % num)

    return num

def writeReiplMethod(reipl_path, reipl_type):
    filename = "%s/reipl_type" % (reipl_path,)

    try:
        f = open(filename, "w")
    except Exception, e:
        message = _("Error: On open, cannot set reIPL method to %(reipl_type)s "
                    "(%(filename)s: %(e)s)" % {'reipl_type': reipl_type,
                                               'filename': filename,
                                               'e': e})
        log.warning(message)
        raise Exception (message)

    try:
        f.write(reipl_type)
        f.flush()
    except Exception, e:
        message = _("Error: On write, cannot set reIPL method to "
                    "%(reipl_type)s (%(filename)s: %(e)s)" \
                  % {'reipl_type': reipl_type, 'filename': filename, 'e': e})
        log.warning(message)
        raise Exception (message)

    try:
        f.close()
    except Exception, e:
        message = _("Error: On close, cannot set reIPL method to "
                    "%(reipl_type)s (%(filename)s: %(e)s)" \
                  % {'reipl_type': reipl_type, 'filename': filename, 'e': e})
        log.warning(message)
        raise Exception (message)

def reIPLonCCW(iplsubdev, reipl_path):
    device = "<unknown>"

    try:
        device = os.readlink("/sys/block/" + iplsubdev + "/device").split('/')[-1]

        writeReiplMethod(reipl_path, 'ccw')

        try:
            f = open("%s/ccw/device" % (reipl_path,), "w")
            f.write(device)
            f.close()
        except Exception, e:
            message = _("Error: Could not set %(device)s as reIPL device "
                        "(%(e)s)" % {'device': device, 'e': e})
            log.warning(message)
            raise Exception (message)

        try:
            f = open("%s/ccw/loadparm" % (reipl_path,), "w")
            f.write("\n")
            f.close()
        except Exception, e:
            message = _("Error: Could not reset loadparm (%s)" % (e,))
            log.warning(message)
            raise Exception (message)

        try:
            f = open("%s/ccw/parm" % (reipl_path,), "w")
            f.write("\n")
            f.close()
        except Exception, e:
            message = _("Warning: Could not reset parm (%s)" % (e,))
            log.warning(message)
            # do NOT raise an exception since this might not exist or not be writable

        log.info("ccw reIPL using DASD %s" % (device,))

    except Exception, e:
        try:
            message = e.args[0]
        except:
            message = e.__str__ ()
        log.info("Caught exception %s", (message,))
        return (message,
                (_("After shutdown, please perform a manual IPL from DASD device %s to continue "
                   "installation") % (device,)))

    return None

def reIPLonFCP(iplsubdev, reipl_path):
    fcpvalue = { "device": "<unknown>", "wwpn": "<unknown>", "lun": "<unknown>" }

    try:
        syspath = "/sys/block/" + iplsubdev + "/device"

        fcpprops = [ ("hba_id", "device"), ("wwpn", "wwpn"), ("fcp_lun", "lun") ]

        # Read in values to change.
        # This way, if we can't set FCP mode, we can tell the user what to manually reboot to.
        for (syspath_property, reipl_property) in fcpprops:
            try:
                f = open(syspath + "/" + syspath_property, "r")
                value = f.read().strip()
                fcpvalue[reipl_property] = value
                f.close()
            except Exception, e:
                message = _("Error: reading FCP property %(syspath_property)s "
                            "for reIPL (%(e)s)" \
                          % {'syspath_property': syspath_property, 'e': e})
                log.warning(message)
                raise Exception (message)

        writeReiplMethod(reipl_path, 'fcp')

        # Write out necessary parameters.
        for (syspath_property, reipl_property) in fcpprops:
            try:
                f = open("%s/fcp/%s" % (reipl_path, reipl_property,), "w")
                f.write(fcpvalue[reipl_property])
                f.close()
            except Exception, e:
                message = _("Error: writing FCP property %(reipl_property)s "
                            "for reIPL (%(e)s)" \
                          % {'reipl_property': reipl_property, 'e': e})
                log.warning(message)
                raise Exception (message)

        defaultprops = [ ("bootprog", "0"), ("br_lba", "0") ]

        # Write out default parameters.
        for (reipl_property, default_value) in defaultprops:
            try:
                f = open("%s/fcp/%s" % (reipl_path, reipl_property,), "w")
                f.write (default_value)
                f.close()
            except Exception, e:
                message = _("Error: writing default FCP property "
                            "%(reipl_property)s for reIPL (%(e)s)" \
                          % {'reipl_property': reipl_property, 'e': e})
                log.warning(message)
                raise Exception (message)

        log.info("fcp reIPL using FCP %(device)s, WWPN %(wwpn)s, LUN %(lun)s" % (fcpvalue))

    except Exception, e:
        try:
            message = e.args[0]
        except:
            message = e.__str__ ()
        log.info("Caught exception %s", (message,))
        return (message,
                (_("After shutdown, please perform a manual IPL from FCP %(device)s with WWPN %(wwpn)s "
                   "and LUN %(lun)s to continue installation") % (fcpvalue)))

    return None


def reIPLtrigger(anaconda):
    if not isS390():
        return
    if anaconda.canReIPL:
        log.info("reIPL configuration successful => reboot")
        os.kill(os.getppid(), signal.SIGUSR2)
    else:
        log.info("reIPL configuration failed => halt")
        os.kill(os.getppid(), signal.SIGUSR1)

def reIPL(anaconda, loader_pid):
    instruction = _("After shutdown, please perform a manual IPL from the device "
                    "now containing /boot to continue installation")

    reipl_path = "/sys/firmware/reipl"

    try:
        ipldev = anaconda.platform.bootDevice().disk.name
    except:
        ipldev = None

    if ipldev is None:
        message = _("Error determining boot device's disk name")
        log.warning(message)
        return (message, instruction)

    message = (_("The mount point /boot or / is on a disk that we are not familiar with"), instruction)
    if ipldev.startswith("dasd"):
        message = reIPLonCCW(ipldev, reipl_path)
    elif ipldev.startswith("sd"):
        message = reIPLonFCP(ipldev, reipl_path)

    if message is None:
        anaconda.canReIPL = True
    else:
        anaconda.canReIPL = False
        log.info(message)

    reIPLtrigger(anaconda)

    # the final return is either None if reipl configuration worked (=> reboot),
    # or a two-item list with errorMessage and rebootInstr (=> shutdown)
    return message

def resetRpmDb(rootdir):
    for rpmfile in glob.glob("%s/var/lib/rpm/__db.*" % rootdir):
        try:
            os.unlink(rpmfile)
        except Exception, e:
            log.debug("error %s removing file: %s" %(e,rpmfile))

def parseNfsUrl(nfsurl):
    options = ''
    host = ''
    path = ''
    if nfsurl:
        s = nfsurl.split(":")
        s.pop(0)
        if len(s) >= 3:
            (options, host, path) = s[:3]
        elif len(s) == 2:
            (host, path) = s
        else:
            host = s[0]
    return (options, host, path)
