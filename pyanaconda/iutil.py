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
import shutil
import signal
import os.path
import errno
import subprocess
import threading
import re

from flags import flags
from constants import *

import gettext
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
log = logging.getLogger("anaconda")
program_log = logging.getLogger("program")

class ExecProduct(object):
    def __init__(self, rc, stdout, stderr):
        self.rc = rc
        self.stdout = stdout
        self.stderr = stderr

#Python reimplementation of the shell tee process, so we can
#feed the pipe output into two places at the same time
class tee(threading.Thread):
    def __init__(self, inputdesc, outputdesc, logmethod, command):
        threading.Thread.__init__(self)
        self.inputdesc = os.fdopen(inputdesc, "r")
        self.outputdesc = outputdesc
        self.logmethod = logmethod
        self.running = True
        self.command = command

    def run(self):
        while self.running:
            try:
                data = self.inputdesc.readline()
            except IOError:
                self.logmethod("Can't read from pipe during a call to %s. "
                               "(program terminated suddenly?)" % self.command)
                break
            if data == "":
                self.running = False
            else:
                self.logmethod(data.rstrip('\n'))
                os.write(self.outputdesc, data)

    def stop(self):
        self.running = False
        return self

def augmentEnv():
    env = os.environ.copy()
    env.update({"LC_ALL": "C",
                "ANA_INSTALL_PATH": ROOT_PATH
               })
    return env

## Run an external program and redirect the output to a file.
# @param command The command to run.
# @param argv A list of arguments.
# @param stdin The file descriptor to read stdin from.
# @param stdout The file descriptor to redirect stdout to.
# @param stderr The file descriptor to redirect stderr to.
# @param root The directory to chroot to before running command.
# @return The return code of command.
def execWithRedirect(command, argv, stdin = None, stdout = None,
                     stderr = None, root = '/', env_prune=[]):
    if flags.testing:
        log.info("not running command because we're testing: %s %s"
                   % (command, " ".join(argv)))
        return 0

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

    orig_stdout = stdout
    if isinstance(stdout, str):
        stdout = os.open(stdout, os.O_RDWR|os.O_CREAT)
        stdoutclose = lambda : os.close(stdout)
    elif isinstance(stdout, int):
        pass
    elif stdout is None or not isinstance(stdout, file):
        stdout = sys.stdout.fileno()

    if isinstance(stderr, str) and isinstance(orig_stdout, str) and stderr == orig_stdout:
        stderr = stdout
    elif isinstance(stderr, str):
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

    env = augmentEnv()

    for var in env_prune:
        if env.has_key(var):
            del env[var]

    try:
        #prepare tee proceses
        proc_std = tee(pstdout, stdout, program_log.info, command)
        proc_err = tee(perrout, stderr, program_log.error, command)

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
# @param fatal Boolean to determine if non-zero exit is fatal.
# @return The output of command from stdout.
def execWithCapture(command, argv, stdin = None, stderr = None, root='/',
                    fatal = False):
    if flags.testing:
        log.info("not running command because we're testing: %s %s"
                    % (command, " ".join(argv)))
        return ""

    def chroot():
        if root is not None:
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

    try:
        proc = subprocess.Popen([command] + argv, stdin=stdin,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                preexec_fn=chroot, cwd=root,
                                env=augmentEnv())

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
        # if we have anything other than a clean exit, and we get the fatal
        # option, raise the OSError.
        if proc.returncode and fatal:
            raise RuntimeError('Error running ' + command + ': Non-zero return code: %s' % proc.returncode)
    except OSError as e:
        log.error ("Error running " + command + ": " + e.strerror)
        raise RuntimeError, "Error running " + command + ": " + e.strerror
    finally:
        closefds()

    return rc

def execWithCallback(command, argv, stdin = None, stdout = None,
                     stderr = None, echo = True, callback = None,
                     callback_data = None, root = '/'):
    if flags.testing:
        log.info("not running command because we're testing: %s %s"
                    % (command, " ".join(argv)))
        return ExecProduct(0, '', '')

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

    log_output = ''
    while 1:
        try:
            s = os.read(p[0], 1)
        except OSError as e:
            if e.errno != 4:
                map(program_log.info, log_output.splitlines())
                raise IOError, e.args

        if echo:
            os.write(stdout, s)
        log_output += s

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

    map(program_log.info, log_output.splitlines())

    log_errors = ''
    while 1:
        try:
            err = os.read(p_stderr[0], 128)
        except OSError as e:
            if e.errno != 4:
                map(program_log.error, log_errors.splitlines())
                raise IOError, e.args
            break
        log_errors += err
        if len(err) < 1:
            break

    os.write(stderr, log_errors)
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

    rc = 1
    if os.WIFEXITED(status):
        rc = os.WEXITSTATUS(status)
    return ExecProduct(rc, log_output , log_errors)

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

def getDirSize(dir):
    """ Get the size of a directory and all its subdirectories.
    @param dir The name of the directory to find the size of.
    @return The size of the directory in kilobytes.
    """
    def getSubdirSize(dir):
        # returns size in bytes
        try:
            mydev = os.lstat(dir)[stat.ST_DEV]
        except OSError as e:
            log.debug("failed to stat %s: %s" % (dir, e))
            return 0

        try:
            dirlist = os.listdir(dir)
        except OSError as e:
            log.debug("failed to listdir %s: %s" % (dir, e))
            return 0

        dsize = 0
        for f in dirlist:
            curpath = '%s/%s' % (dir, f)
            try:
                sinfo = os.lstat(curpath)
            except OSError as e:
                log.debug("failed to stat %s/%s: %s" % (dir, f, e))
                continue

            if stat.S_ISDIR(sinfo[stat.ST_MODE]):
                if os.path.ismount(curpath):
                    continue
                if mydev == sinfo[stat.ST_DEV]:
                    dsize += getSubdirSize(curpath)
            elif stat.S_ISREG(sinfo[stat.ST_MODE]):
                dsize += sinfo[stat.ST_SIZE]

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

    return long(mem)

## Create a directory path.  Don't fail if the directory already exists.
# @param dir The directory path to create.
def mkdirChain(dir):
    try:
        os.makedirs(dir, 0755)
    except OSError as e:
        try:
            if e.errno == errno.EEXIST and stat.S_ISDIR(os.stat(dir).st_mode):
                return
        except OSError:
            pass

        log.error("could not create directory %s: %s" % (dir, e.strerror))

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

## Get the SPARC machine variety type.
# @return The SPARC machine type, or 0 if not SPARC.
def getSparcMachine():
    if not isSparc():
        return 0

    machine = None


    f = open('/proc/cpuinfo', 'r')
    lines = f.readlines()
    f.close()
    for line in lines:
        if line.find('type') != -1:
            machine = line.split(':')[1].strip()
            return machine

    return None

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
                'PS3'      : 'PS3',
                'PowerNV'  : 'pSeries'
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

## Get the ARM processor variety.
# @return The ARM processor variety type, or 0 if not ARM.
def getARMMachine():
    if not isARM():
        return 0

    if flags.armPlatform:
        return flags.armPlatform

    armMachine = os.uname()[2].rpartition('.' )[2]

    if armMachine.startswith('arm'):
        return None
    else:
        return armMachine


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
    elif not os.path.isfile(DMI_CHASSIS_VENDOR):
        mactel = False
    else:
        buf = open(DMI_CHASSIS_VENDOR).read()
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

def isPPC(bits=None):
    arch = os.uname()[4]

    if bits is None:
        if arch == 'ppc' or arch == 'ppc64':
            return True
    elif bits == 32:
        if arch == 'ppc':
            return True
    elif bits == 64:
        if arch == 'ppc64':
            return True

    return False

def isS390():
    return os.uname()[4].startswith('s390')

def isIA64():
    return os.uname()[4] == 'ia64'

def isAlpha():
    return os.uname()[4].startswith('alpha')

def isSparc():
    return os.uname()[4].startswith('sparc')

def isARM():
    return os.uname()[4].startswith('arm')

def getArch():
    if isX86(bits=32):
        return 'i386'
    elif isX86(bits=64):
        return 'x86_64'
    elif isPPC(bits=32):
        return 'ppc'
    elif isPPC(bits=64):
        return 'ppc64'
    elif isAlpha():
        return 'alpha'
    elif isSparc():
        return 'sparc'
    elif isARM():
        return 'arm'
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
    """ Signal the kernel that the specified device has changed.

        Exceptions raised: ValueError, IOError
    """
    log.debug("notifying kernel of '%s' event on device %s" % (action, path))
    path = os.path.join(path, "uevent")
    if not path.startswith("/sys/") or not os.access(path, os.W_OK):
        log.debug("sysfs path '%s' invalid" % path)
        raise ValueError("invalid sysfs path")

    f = open(path, "a")
    f.write("%s\n" % action)
    f.close()

def get_sysfs_path_by_name(dev_node, class_name="block"):
    """ Return sysfs path for a given device.

        For a device node (e.g. /dev/vda2) get the respective sysfs path
        (e.g. /sys/class/block/vda2). This also has to work for device nodes
        that are in a subdirectory of /dev like '/dev/cciss/c0d0p1'.
     """
    dev_name = os.path.basename(dev_node)
    if dev_node.startswith("/dev/"):
        dev_name = dev_node[5:].replace("/", "!")
    sysfs_class_dir = "/sys/class/%s" % class_name
    dev_path = os.path.join(sysfs_class_dir, dev_name)
    if os.path.exists(dev_path):
        return dev_path
    else:
        raise RuntimeError("get_sysfs_path_by_name: Could not find sysfs path "
                           "for '%s' (it is not at '%s')" % (dev_node, dev_path))

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

def reIPL(ipldev):
    try:
        rc = execWithRedirect("chreipl", ["node", "/dev/" + ipldev],
                              stdout = "/dev/tty5",
                              stderr = "/dev/tty5")
    except RuntimeError as e:
        rc = True
        log.info("Unable to set reIPL device to %s: %s",
                 ipldev, e)

    if rc:
        devstring = None

        for disk in anaconda.storage.disks:
            if disk.name == ipldev:
                devstring = disk.description
                break

        if devstring is None:
            devstring = _("the device containing /boot")

        message = _("After shutdown, please perform a manual IPL from %s "
                    "to continue installation." % devstring)

        log.info("reIPL configuration failed")
        #os.kill(os.getppid(), signal.SIGUSR1)
    else:
        message = None
        log.info("reIPL configuration successful")
        #os.kill(os.getppid(), signal.SIGUSR2)

    return message

def resetRpmDb():
    for rpmfile in glob.glob("%s/var/lib/rpm/__db.*" % ROOT_PATH):
        try:
            os.unlink(rpmfile)
        except OSError as e:
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

def insert_colons(a_string):
    """
    Insert colon between every second character.

    E.g. creates 'al:go:ri:th:ms' from 'algoritms'. Useful for formatting MAC
    addresses and wwids for output.
    """
    suffix = a_string[-2:]
    if len(a_string) > 2:
        return insert_colons(a_string[:-2]) + ':' + suffix
    else:
        return suffix

def add_po_path(module, dir):
    """ Looks to see what translations are under a given path and tells
    the gettext module to use that path as the base dir """
    for d in os.listdir(dir):
        if not os.path.isdir("%s/%s" %(dir,d)):
            continue
        if not os.path.exists("%s/%s/LC_MESSAGES" %(dir,d)):
            continue
        for basename in os.listdir("%s/%s/LC_MESSAGES" %(dir,d)):
            if not basename.endswith(".mo"):
                continue
            log.info("setting %s as translation source for %s" %(dir, basename[:-3]))
            module.bindtextdomain(basename[:-3], dir)

def setup_translations(module):
    if os.path.isdir(TRANSLATIONS_UPDATE_DIR):
        add_po_path(module, TRANSLATIONS_UPDATE_DIR)
    module.textdomain("anaconda")

def copy_to_sysimage(source):
    if not os.access(source, os.R_OK):
        log.info("copy_to_sysimage: source '%s' does not exist." % source)
        return False

    target = ROOT_PATH + source
    target_dir = os.path.dirname(target)
    log.debug("copy_to_sysimage: '%s' -> '%s'." % (source, target))
    if not os.path.isdir(target_dir):
        os.makedirs(target_dir)
    shutil.copy(source, target)
    return True

def get_sysfs_attr(path, attr):
    if not attr:
        log.debug("get_sysfs_attr() called with attr=None")
        return None

    attribute = "/sys%s/%s" % (path, attr)
    attribute = os.path.realpath(attribute)

    if not os.path.isfile(attribute) and not os.path.islink(attribute):
        log.warning("%s is not a valid attribute" % (attr,))
        return None

    return open(attribute, "r").read().strip()

def find_program_in_path(prog, raise_on_error=False):
    for d in os.environ["PATH"].split(os.pathsep):
        full = os.path.join(d, prog)
        if os.access(full, os.X_OK):
            return full

    if raise_on_error:
        raise RuntimeError("Unable to locate a needed executable: '%s'" % prog)
    return None

def fork_orphan():
    """Forks an orphan.

    Returns 1 in the parent and 0 in the orphaned child.
    """
    intermediate = os.fork()
    if not intermediate:
        if os.fork():
            # the intermediate child dies
            os._exit(0)
        return 0
    # the original process waits for the intermediate child
    os.waitpid(intermediate, 0)
    return 1

def lsmod():
    """ Returns list of names of all loaded modules. """
    with open("/proc/modules") as f:
        lines = f.readlines()
    return [l.split()[0] for l in lines]

def _run_systemctl(command, service):
    """
    Runs 'systemctl command service.service'

    @return: exit status of the systemctl

    """

    service_name = service + ".service"
    ret = execWithRedirect("systemctl", [command, service_name], stdin=None,
                           stdout="/dev/tty5", stderr="/dev/tty5")

    return ret

def start_service(service):
    return _run_systemctl("start", service)

def stop_service(service):
    return _run_systemctl("stop", service)

def restart_service(service):
    return _run_systemctl("restart", service)

def service_running(service):
    ret = _run_systemctl("status", service)

    return ret == 0

def dracut_eject(device):
    """
    Use dracut shutdown hook to eject media after the system is shutdown.
    This is needed because we are running from the squashfs.img on the media
    so ejecting too early will crash the installer.
    """
    if not device:
        return

    try:
        if not os.path.exists(DRACUT_SHUTDOWN_EJECT):
            f = open(DRACUT_SHUTDOWN_EJECT, "w")
            f.write("#!/bin/sh\n")
            f.write("# Created by Anaconda\n")
        else:
            f = open(DRACUT_SHUTDOWN_EJECT, "a")

        f.write("eject %s\n" % (device,))
        f.close()
        os.chmod(DRACUT_SHUTDOWN_EJECT, 0755)
        log.info("Wrote dracut shutdown eject hook for %s" % (device,))
    except Exception, e:
        log.error("Error writing dracut shutdown eject hook for %s: %s" % (device, e))

def get_option_value(opt_name, options):
    """ Return the value of a named option in the specified options string. """
    for opt in options.split(","):
        if "=" not in opt:
            continue

        name, val = opt.split("=")
        if name == opt_name:
            return val.strip()

def vtActivate(num):
    """
    Try to switch to tty number $num.

    @type num: int
    @return: whether the switch was successful or not
    @rtype: bool

    """

    try:
        ret = execWithRedirect("chvt", [str(num)], stdout="/dev/tty5",
                                stderr="/dev/tty5")
    except OSError as oserr:
        ret = -1
        log.error("Failed to run chvt: %s", oserr.strerror)

    if ret != 0:
        log.error("Failed to switch to tty%d", num)

    return ret == 0

class ProxyStringError(Exception):
    pass

class ProxyString(object):
    """ Handle a proxy url
    """
    def __init__(self, url=None, protocol="http://", host=None, port="3128",
                 username=None, password=None):
        """ Initialize with either url
        ([protocol://][username[:password]@]host[:port]) or pass host and
        optionally:

        protocol    http, https, ftp
        host        hostname without protocol
        port        port number (defaults to 3128)
        username    username
        password    password

        The str() of the object is the full proxy url

        ProxyString.url is the full url including username:password@
        ProxyString.noauth_url is the url without username:password@
        """
        self.url = url
        self.protocol = protocol
        self.host = host
        self.port = str(port)
        self.username = username
        self.password = password
        self.proxy_auth = ""
        self.noauth_url = None

        if url:
            self.parse_url()
        elif not host:
            raise ProxyStringError("No host url")
        else:
            self.parse_components()

    def parse_url(self):
        """ Parse the proxy url into its component pieces
        """
        # NOTE: If this changes, update tests/regex/proxy.py
        #
        # proxy=[protocol://][username[:password]@]host[:port][path]
        # groups
        # 1 = protocol
        # 2 = username:password@
        # 3 = username
        # 4 = password
        # 5 = hostname
        # 6 = port
        # 7 = extra
        pattern = re.compile("([A-Za-z]+://)?(([A-Za-z0-9]+)(:[^:@]+)?@)?([^:/]+)(:[0-9]+)?(/.*)?")
        m = pattern.match(self.url)
        if not m:
            raise ProxyStringError("malformed url, cannot parse it.")

        # If no protocol was given default to http.
        if m.group(1):
            self.protocol = m.group(1)
        else:
            self.protocol = "http://"

        if m.group(3):
            self.username = m.group(3)

        if m.group(4):
            # Skip the leading colon
            self.password = m.group(4)[1:]

        if m.group(5):
            self.host = m.group(5)
            if m.group(6):
                # Skip the leading colon
                self.port = m.group(6)[1:]
        else:
            raise ProxyStringError("url has no host component")

        self.parse_components()

    def parse_components(self):
        """ Parse the components of a proxy url into url and noauth_url
        """
        if self.username or self.password:
            self.proxy_auth = "%s:%s@" % (self.username or "",
                                          self.password or "")

        self.url = self.protocol + self.proxy_auth + self.host + ":" + self.port
        self.noauth_url = self.protocol + self.host + ":" + self.port

    @property
    def dict(self):
        """ return a dict of all the elements of the proxy string
        url, noauth_url, protocol, host, port, username, password
        """
        components = ["url", "noauth_url", "protocol", "host", "port",
                      "username", "password"]
        return dict([(k, getattr(self, k)) for k in components]) 

    def __str__(self):
        return self.url

