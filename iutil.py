#
# iutil.py - generic install utility functions
#
# Erik Troan <ewt@redhat.com>
#
# Copyright 1999-2001 Red Hat, Inc.
#
# This software may be freely redistributed under the terms of the GNU
# library public license.
#
# You should have received a copy of the GNU Library Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

import types, os, sys, isys, select, string, stat, signal
import os.path
from rhpl.log import log

memoryOverhead = 0

def setMemoryOverhead(amount):
    global memoryOverhead

    memoryOverhead = amount

def getArch ():
    arch = os.uname ()[4]
    if (len (arch) == 4 and arch[0] == 'i' and
        arch[2:4] == "86"):
        arch = "i386"

    if arch == "sparc64":
        arch = "sparc"

    if arch == "s390x":
        arch = "s390"

    return arch

def getfd(filespec, readOnly = 0):
    if type(filespec) == types.IntType:
	return filespec
    if filespec == None:
	filespec = "/dev/null"

    flags = os.O_RDWR | os.O_CREAT
    if (readOnly):
	flags = os.O_RDONLY
    return os.open(filespec, flags)

def execWithRedirect(command, argv, stdin = 0, stdout = 1, stderr = 2,	
		     searchPath = 0, root = '/', newPgrp = 0,
		     ignoreTermSigs = 0):
    stdin = getfd(stdin)
    if stdout == stderr:
	stdout = getfd(stdout)
	stderr = stdout
    else:
	stdout = getfd(stdout)
	stderr = getfd(stderr)

    if not os.access (root + command, os.X_OK):
	raise RuntimeError, command + " can not be run"

    childpid = os.fork()
    if (not childpid):
        if (root and root != '/'): 
	    os.chroot (root)
	    os.chdir("/")

	if ignoreTermSigs:
	    signal.signal(signal.SIGTSTP, signal.SIG_IGN)
	    signal.signal(signal.SIGINT, signal.SIG_IGN)

	if type(stdin) == type("a"):
	    stdin == os.open(stdin, os.O_RDONLY)
	if type(stdout) == type("a"):
	    stdout == os.open(stdout, os.O_RDWR)
	if type(stderr) == type("a"):
	    stderr = os.open(stderr, os.O_RDWR)

	if stdin != 0:
	    os.dup2(stdin, 0)
	    os.close(stdin)
	if stdout != 1:
	    os.dup2(stdout, 1)
	    if stdout != stderr:
		os.close(stdout)
	if stderr != 2:
	    os.dup2(stderr, 2)
	    os.close(stderr)

	if (searchPath):
	    os.execvp(command, argv)
	else:
	    os.execv(command, argv)

	sys.exit(1)

    if newPgrp:
	os.setpgid(childpid, childpid)
	oldPgrp = os.tcgetpgrp(0)
	os.tcsetpgrp(0, childpid)

    status = -1
    try:
        (pid, status) = os.waitpid(childpid, 0)
    except OSError, (errno, msg):
        print __name__, "waitpid:", msg

    if newPgrp:
	os.tcsetpgrp(0, oldPgrp)

    return status

def execWithCapture(command, argv, searchPath = 0, root = '/', stdin = 0,
		    catchfd = 1, closefd = -1):

    if not os.access (root + command, os.X_OK):
	raise RuntimeError, command + " can not be run"

    (read, write) = os.pipe()

    childpid = os.fork()
    if (not childpid):
        if (root and root != '/'): os.chroot (root)
	os.dup2(write, catchfd)
	os.close(write)
	os.close(read)

	if closefd != -1:
	    os.close(closefd)

	if stdin:
	    os.dup2(stdin, 0)
	    os.close(stdin)

	if (searchPath):
	    os.execvp(command, argv)
	else:
	    os.execv(command, argv)

	sys.exit(1)

    os.close(write)

    rc = ""
    s = "1"
    while (s):
	select.select([read], [], [])
	s = os.read(read, 1000)
	rc = rc + s

    os.close(read)

    try:
        os.waitpid(childpid, 0)
    except OSError, (errno, msg):
        print __name__, "waitpid:", msg

    return rc

def copyFile(source, to, pw = None):
    f = os.open(source, os.O_RDONLY)
    t = os.open(to, os.O_RDWR | os.O_TRUNC | os.O_CREAT)

    if pw:
	(fn, title, text) = pw
	total = os.path.getsize(source)
	win = fn(title, text, total)

    try:
	count = os.read(f, 262144)
	total = 0
	while (count):
	    os.write(t, count)

	    total = total + len(count)
	    if pw:
		win.set(total)
	    count = os.read(f, 16384)
    finally:
	os.close(f)
	os.close(t)

	if pw:
	    win.pop()


# this is in kilobytes
def memInstalled(corrected = 1):
    global memoryOverhead

    if not os.access('/proc/e820info', os.R_OK):
        f = open("/proc/meminfo", "r")
        mem = f.readlines()[1]
        del f

        fields = string.split(mem)
        mem = int(long(fields[1]) / 1024)
    else:
        f = open("/proc/e820info", "r")
        lines = f.readlines()
        mem = 0
        for line in lines:
            fields = string.split(line)
            if fields[3] == "(usable)":
                mem = mem + (string.atol(fields[0], 16) / 1024)
                
    if corrected:
        mem = mem - memoryOverhead

    return int(mem)

# try to keep 2.4 kernel swapper happy!
def swapSuggestion():
    mem = memInstalled(corrected=0)/1024
    mem = ((mem/16)+1)*16
    log("Detected %sM of memory", mem)
    if mem < 128:
        minswap = 96
        maxswap = 192
    else:
        if mem > 1000:
            minswap = 1000
            maxswap = 2000
        else:
            minswap = mem
            maxswap = 2*mem
            
    log("Swap attempt of %sM to %sM", minswap, maxswap)

    return (minswap, maxswap)

    
# this is a mkdir that won't fail if a directory already exists and will
# happily make all of the directories leading up to it. 
def mkdirChain(dir):
    if (os.path.isdir(dir)): return
    elements = string.splitfields(dir, "/")

    if (len(elements[0])):
	which = 1
	path = elements[0] 
    else:
	which = 2
	path = "/" + elements[1]

    if (not os.path.isdir(path)): 
	os.mkdir(path, 0755)

    while (which < len(elements)):
	path = path + "/" + elements[which]
	which = which + 1
	
	if (not os.path.isdir(path)): 
	    os.mkdir(path, 0755)

def makerelname(relpath, filename):
    if relpath != '':
        return relpath+'/'+filename
    else:
        return filename
    
    
def findtz(basepath, relpath):
    tzdata = []
    for n in os.listdir(basepath+'/'+relpath):
        timezone = makerelname(relpath, n)
        if relpath != '':
            timezone = relpath+'/'+n
        else:
            timezone = n
            
        filestat = os.lstat(basepath+'/'+timezone)
        [filemode] = filestat[:1]
        
        if (not (stat.S_ISLNK(filemode) or
                 stat.S_ISREG(filemode) or
                 stat.S_ISDIR(filemode))):
            continue
        elif n[:1] >= 'A' and n[:1] <= 'Z':
            if stat.S_ISDIR(filemode):
                tmptzdata = findtz(basepath, timezone)
            else:
                tmptzdata = [timezone]
                    
        for m in tmptzdata:
            if tzdata == []:
                tzdata = [m]
            else:
                tzdata.append(m)

        tzdata.sort()
                            
    return tzdata

def rmrf (path):
    # this is only the very simple case.
    if os.path.isdir(path):
        files = os.listdir (path)
    else:
        os.unlink(path)
        return
    for file in files:
        if os.path.isdir(path + '/' + file):
            rmrf (path + '/' + file)
        else:
            os.unlink (path + '/' + file)
    os.rmdir (path)

def validUser (user):
    if not user[0] in string.letters:
        return 0

    for letter in user:
        if (letter == ':'
            or letter == ','
            or letter == '\n'
            or ord (letter) < 33):
            return 0

    return 1

def setClock (root):
    # eeeeew, inline shell. ;)
    args = ("bash", "-c", """
if [ -f /etc/sysconfig/clock ]; then
   . /etc/sysconfig/clock
   
   # convert old style clock config to new values
   if [ "${CLOCKMODE}" = "GMT" ]; then
      UTC=true
   elif [ "${CLOCKMODE}" = "ARC" ]; then
      ARC=true
   fi
fi

CLOCKFLAGS="--hctosys"

case "$UTC" in
   yes|true)
    CLOCKFLAGS="$CLOCKFLAGS -u";
     ;;
esac

case "$ARC" in
     yes|true)
        CLOCKFLAGS="$CLOCKFLAGS -A";
     ;;
esac
case "$SRM" in
     yes|true)
        CLOCKFLAGS="$CLOCKFLAGS -S";
     ;;
esac
/sbin/hwclock $CLOCKFLAGS
""")
    execWithRedirect('/bin/sh', args, stdin = None,
                     stdout = None, stderr = None,
                     root = root)

def swapAmount():
    f = open("/proc/meminfo", "r")
    mem = f.readlines()[2]
    del f

    fields = string.split(mem)
    mem = int(long (fields[1]) / 1024)

    return mem
        
def copyDeviceNode(src, dest):
    """Copies the device node at src to dest by looking at the type of device,
    major, and minor of src and doing a new mknod at dest"""

    filestat = os.lstat(src)
    mode = filestat[stat.ST_MODE]
    if stat.S_ISBLK(mode):
        type = stat.S_IFBLK
    elif stat.S_ISCHR(mode):
        type = stat.S_IFCHR
    else:
        # XXX should we just fallback to copying normally?
        raise RuntimeError, "Tried to copy %s which isn't a device node" % (src,)

    isys.mknod(dest, mode | type, filestat.st_rdev)

# make the device nodes for all of the drives on the system
def makeDriveDeviceNodes():
    hardDrives = isys.hardDriveDict()
    for drive in hardDrives.keys():
        isys.makeDevInode(drive, "/dev/%s" % (drive,))

        if drive.startswith("hd"):
            num = 32
        else:
            num = 15

        for i in range(1, num):
            dev = "%s%d" % (drive, i)
            isys.makeDevInode(dev, "/dev/%s" % (dev,))

    cdroms = isys.cdromList()
    for drive in cdroms:
        isys.makeDevInode(drive, "/dev/%s" % (drive,))
    
def needsEnterpriseKernel():
    rc = 0

    try:
        f = open("/proc/e820info", "r")
    except IOError:
        return 0
    for l in f.readlines():
	l = string.split(l)
	if l[3] == '(reserved)': continue

	regionEnd = (string.atol(l[0], 16) - 1) + string.atol(l[2], 16)
	if regionEnd > 0xffffffffL:
	    rc = 1

    return rc

