#
# iutil.py - generic install utility functions
#
# Erik Troan <ewt@redhat.com>
#
# Copyright 1999-2003 Red Hat, Inc.
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
from flags import flags

def getArch ():
    arch = os.uname ()[4]
    if (len (arch) == 4 and arch[0] == 'i' and
        arch[2:4] == "86"):
        arch = "i386"

    if arch == "sparc64":
        arch = "sparc"

    if arch == "ppc64":
        arch = "ppc"

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
    if not searchPath and not os.access (root + command, os.X_OK):
	raise RuntimeError, command + " can not be run"

    childpid = os.fork()
    if (not childpid):
        if (root and root != '/'): 
	    os.chroot (root)
	    os.chdir("/")

	if ignoreTermSigs:
	    signal.signal(signal.SIGTSTP, signal.SIG_IGN)
	    signal.signal(signal.SIGINT, signal.SIG_IGN)

        stdin = getfd(stdin)
        if stdout == stderr:
            stdout = getfd(stdout)
            stderr = stdout
        else:
            stdout = getfd(stdout)
            stderr = getfd(stderr)

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

        try:
            if (searchPath):
                os.execvp(command, argv)
            else:
                os.execv(command, argv)
        except OSError:
            # let the caller deal with the exit code of 1.
            pass

	os._exit(1)

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
		    stderr = 2, catchfd = 1, closefd = -1):

    if not searchPath and not os.access (root + command, os.X_OK):
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

        if stderr == sys.stdout:
            stderr = sys.stdout.fileno()
        else:
            stderr = getfd(stderr)

	if stderr != 2:
	    os.dup2(stderr, 2)
	    os.close(stderr)

	if (searchPath):
	    os.execvp(command, argv)
	else:
	    os.execv(command, argv)

	os._exit(1)

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

# return size of directory (and subdirs) in kilobytes
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

# this is in kilobytes - returns amount of RAM not used by /tmp
def memAvailable():
    tram = memInstalled()

    ramused = getDirSize("/tmp")
    if os.path.isdir("/tmp/ramfs"):
        ramused += getDirSize("/tmp/ramfs")

    return tram - ramused

# this is in kilobytes
def memInstalled():
    if not os.access('/proc/e820info', os.R_OK):
        f = open("/proc/meminfo", "r")
        lines = f.readlines()
        f.close()

        for l in lines:
            if l.startswith("MemTotal:"):
                fields = string.split(l)
                mem = fields[1]
                break
    else:
        f = open("/proc/e820info", "r")
        lines = f.readlines()
        mem = 0
        for line in lines:
            fields = string.split(line)
            if fields[3] == "(usable)":
                mem = mem + (string.atol(fields[0], 16) / 1024)

    return int(mem)

# try to keep 2.4 kernel swapper happy!
def swapSuggestion(quiet=0):
    mem = memInstalled()/1024
    mem = ((mem/16)+1)*16
    if not quiet:
	log("Detected %sM of memory", mem)
	
    if mem < 128:
        minswap = 96
        maxswap = 192
    else:
        if mem > 2000:
            minswap = 2000
            maxswap = 2000 + mem # 2x2G + mem-2G
        elif mem > 1000:
            minswap = 1000
            maxswap = 2000
        else:
            minswap = mem
            maxswap = 2*mem

    if not quiet:
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
                tzdata.extend(findtz(basepath, timezone))
            else:
                tzdata.append(timezone)

    tzdata.sort()
                            
    return tzdata

def rmrf (path):
    # this is only the very simple case.
    # NOTE THAT THIS IS RACY IF USED ON AN INSTALLED SYSTEM
    # IT IS ONLY SAFE FOR ANACONDA AS A CONTAINED ENVIRONMENT
    if os.path.isdir(path):
        files = os.listdir (path)
    else:
        os.unlink(path)
        return
    for file in files:
        if (not os.path.islink(path + '/' + file) and
            os.path.isdir(path + '/' + file)):
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
    try:
        execWithRedirect('/bin/bash', args, stdin = None,
                         stdout = None, stderr = None,
                         root = root)
    except RuntimeError:
        log("Failed to set clock properly.  Going to try to continue anyway.")

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

# make the device-mapper control node
def makeDMNode(root="/"):
    major = minor = None

    for (fn, devname, val) in ( ("/proc/devices", "misc", "major"),
                                ("/proc/misc", "device-mapper", "minor") ):
        f = open(fn)
        lines = f.readlines()
        f.close()
        for line in lines:
            try:
                (num, dev) = line.strip().split(" ")
            except:
                continue
            if dev == devname:
                s = "%s = int(num)" %(val,)
                exec s
                break

#    print "major is %s, minor is %s" %(major, minor)
    if major is None or minor is None:
        return
    mkdirChain(root + "/dev/mapper")
    isys.mknod(root + "/dev/mapper/control", stat.S_IFCHR | 0600,
               isys.makedev(major, minor))


# make the device nodes for all of the drives on the system
def makeDriveDeviceNodes():
    import raid
    
    hardDrives = isys.hardDriveDict()
    for drive in hardDrives.keys():
        isys.makeDevInode(drive, "/dev/%s" % (drive,))

        if drive.startswith("hd"):
            num = 32
        elif drive.startswith("dasd"):
            num = 4
        else:
            num = 15

        if (drive.startswith("cciss") or drive.startswith("ida") or
            drive.startswith("rd") or drive.startswith("sx8")):
            sep = "p"
        else:
            sep = ""

        for i in range(1, num):
            dev = "%s%s%d" % (drive, sep, i)
            isys.makeDevInode(dev, "/dev/%s" % (dev,))

    isys.flushDriveDict()
    cdroms = isys.cdromList()
    for drive in cdroms:
        isys.makeDevInode(drive, "/dev/%s" % (drive,))

    for mdMinor in range(0, 32):
        md = "md%d" %(mdMinor,)
        isys.makeDevInode(md, "/dev/%s" %(md,))

    # make the node for the device mapper
    makeDMNode()
    
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

#
# scan /proc/mounts to see if we've already have USB mounted
#
# kernel can fall over if we mount it twice on some hw (bug #71554)
#
def isUSBDevFSMounted():
    try:
	f = open("/proc/mounts", "r")
	lines = f.readlines()
	f.close()
	for l in lines:
	    if string.find(l, "usbfs") != -1:
		return 1
	    if string.find(l, "usbdevfs") != -1:
		return 1
    except:
	log("In isUSBMounted, failed to open /proc/mounts")
	return 0

    return 0

# this is disgusting and I feel very dirty
def hasiSeriesNativeStorage():
    if getArch() != "ppc":
        return

    f = open("/proc/modules", "r")
    lines = f.readlines()
    f.close()

    for line in lines:
        if line.startswith("ibmsis"):
            return 1
        if line.startswith("ipr"):
            return 1

    return 0

# return the ppc machine variety type
def getPPCMachine():
    machine = None
    # ppc machine hash
    ppcType = { 'Mac'      : 'PMac',
                'Book'     : 'PMac',
                'CHRP IBM' : 'pSeries',
                'iSeries'  : 'iSeries',
                'PReP'     : 'PReP',
                'CHRP'     : 'pSeries',
                'Amiga'    : 'APUS',
                'Gemini'   : 'Gemini',
                'Shiner'   : 'ANS',
                'BRIQ'     : 'BRIQ',
                'Teron'    : 'Teron',
                'AmigaOne' : 'Teron'
                }

    if getArch() != "ppc":
        return 0

    f = open('/proc/cpuinfo', 'r')
    lines = f.readlines()
    f.close()
    for line in lines:
        if line.find('machine') != -1:
            machine = line.split(':')[1]
            break

    if machine is None:
        log("Unable to find PowerPC machine type")
        return

    for type in ppcType.items():
        if machine.find(type[0]) != -1:
            return type[1]

    log("Unknown PowerPC machine type: %s" %(machine,))
    return 0

# return the pmac machine id
def getPPCMacID():
    machine = None
    
    if getArch() != "ppc":
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

    log("WARNING: No Power Mac machine id")
    return 0

# return the pmac generation
def getPPCMacGen():
    # XXX: should NuBus be here?
    pmacGen = ['OldWorld', 'NewWorld', 'NuBus']
    
    if getArch() != "ppc":
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
        log("Unable to find pmac-generation")

    for type in pmacGen:
      if gen.find(type) != -1:
          return type

    log("Unknown Power Mac generation: %s" %(gen,))
    return 0

# return if pmac machine is it an iBook/PowerBook
def getPPCMacBook():
    if getArch() != "ppc":
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

def writeRpmPlatform(root="/"):
    import rhpl.arch

    if flags.test:
        return
    if os.access("%s/etc/rpm/platform" %(root,), os.R_OK):
        return
    if not os.access("%s/etc/rpm" %(root,), os.X_OK):
        os.mkdir("%s/etc/rpm" %(root,))

    myarch = rhpl.arch.canonArch

    # now allow an override with rpmarch=i586 on the command line (#101971)
    f = open("/proc/cmdline", "r")
    buf = f.read()
    f.close()
    args = buf.split(" ")
    for arg in args:
        if arg.startswith("rpmarch="):
            myarch = arg[8:]
        
    f = open("%s/etc/rpm/platform" %(root,), 'w+')
    f.write("%s-redhat-linux\n" %(myarch,))
    f.close()

    # FIXME: writing /etc/rpm/macros feels wrong somehow
    # temporary workaround for #92285
    if os.access("%s/etc/rpm/macros" %(root,), os.R_OK):
        return
    if not (myarch.startswith("ppc64") or
            myarch in ("s390x", "sparc64", "x86_64", "ia64")):
        return
    f = open("%s/etc/rpm/macros" %(root,), 'w+')
    f.write("%_transaction_color   3\n")
    f.close()
    
