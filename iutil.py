import types, os, sys, isys, select, string, stat, signal
import os.path
from log import log

memoryOverhead = 0
floppyDevice = None

def setMemoryOverhead(amount):
    global memoryOverhead

    memoryOverhead = amount

def SetFdDevice():
    global floppyDevice

    if floppyDevice:
	return floppydevice

    floppyDevice = "fd0"
    if iutil.getArch() == "sparc":
	try:
	    f = open(floppyDevice, "r")
	except IOError, (errnum, msg):
	    if errno.errorcode[errnum] == 'ENXIO':
		floppyDevice = "fd1"
	else:
	    f.close()
    elif iutil.getArch() == "alpha":
	pass
    elif iutil.getArch() == "s390":
	return
    elif iutil.getArch() == "s390x":
	return
    elif iutil.getArch() == "i386" or iutil.getArch() == "ia64":
	# Look for the first IDE floppy device
	drives = isys.floppyDriveDict()
	if not drives:
	    log("no IDE floppy devices found")
	    return 0

	floppyDrive = drives.keys()[0]
	# need to go through and find if there is an LS-120
	for dev in drives.keys():
	    if re.compile(".*[Ll][Ss]-120.*").search(drives[dev]):
		floppyDrive = dev

	# No IDE floppy's -- we're fine w/ /dev/fd0
	if not floppyDrive: return

	if iutil.getArch() == "ia64":
	    floppyDevice = floppyDrive
	    log("anaconda floppy device is %s", floppyDevice)
	    return

	# Look in syslog for a real fd0 (which would take precedence)
	try:
	    f = open("/tmp/syslog", "r")
	except IOError:
	    return
	for line in f.readlines():
	    # chop off the loglevel (which init's syslog leaves behind)
	    line = line[3:]
	    match = "Floppy drive(s): "
	    if match == line[:len(match)]:
		# Good enough
		floppyDrive = "fd0"
		break

	floppyDevice = floppyDrive
    else:
	raise SystemError, "cannot determine floppy device for this arch"

    log("anaconda floppy device is %s", floppyDevice)

    return floppyDevice

def getArch ():
    arch = os.uname ()[4]
    if (len (arch) == 4 and arch[0] == 'i' and
        arch[2:4] == "86"):
        arch = "i386"

    if arch == "sparc64":
        arch = "sparc"

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
	    isys.chroot (root)
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
        if (root and root != '/'): isys.chroot (root)
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


def memInstalled(corrected = 1):
    global memoryOverhead

    f = open("/proc/meminfo", "r")
    mem = f.readlines()[1]
    del f

    fields = string.split(mem)
    mem = int(long(fields[1]) / 1024)

    if corrected:
	mem = mem - memoryOverhead

    return mem

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

#
# get default runlevel - only for use in reconfig mode
#
def getDefaultRunlevel ():
    inittab = open ('/etc/inittab', 'r')
    lines = inittab.readlines ()
    inittab.close ()
    for line in lines:
        if len (line) > 3 and line[:3] == "id:":
            fields = string.split (line, ':')
            return fields[1]

    return None

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
    files = os.listdir (path)
    for file in files:
        if os.path.isdir(path + '/' + file):
            rmrf (path + '/' + file)
        else:
            os.unlink (path + '/' + file)
    os.rmdir (path)

def validUser (user):
    if len (user) > 8:
        return 0
    
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

class InstSyslog:
    def __init__ (self, root, log):
        self.pid = os.fork ()
        if not self.pid:
            # look on PYTHONPATH first, so we use updated anaconda
            path = None
            if os.environ.has_key('PYTHONPATH'):
                for f in string.split(os.environ['PYTHONPATH'], ":"):
                    if os.access (f+"/anaconda", os.X_OK):
                        path = f+"/anaconda"
                        break
                
            if not path:
                if os.access ("./anaconda", os.X_OK):
                    path = "./anaconda"
                elif os.access ("/usr/bin/anaconda.real", os.X_OK):
                    path = "/usr/bin/anaconda.real"
                else:
                    path = "/usr/bin/anaconda"
                    
            os.execv (path, ("syslogd", "--syslogd", root, log))

    def __del__ (self):
        os.kill (self.pid, 15)
	os.wait (self.pid)
        
# XXX this doesn't work!
#
# funky, but importing dispatch at the top of iutil breaks things!?!
def makeBootdisk (intf):
    # this is faster then waiting on mkbootdisk to fail

    import dispatch
    return dispatch.DISPATCH_NOOP

    device = floppyDevice
    file = "/tmp/floppy"
    isys.makeDevInode(device, file)
    try:
	fd = os.open(file, os.O_RDONLY)
    except:
	import dispatch
	return dispatch.DISPATCH_BACK
    os.close(fd)

    kernel = self.hdList['kernel']
    kernelTag = "-%s-%s" % (kernel[rpm.RPMTAG_VERSION],
			    kernel[rpm.RPMTAG_RELEASE])

    w = self.intf.waitWindow (_("Creating"), _("Creating boot disk..."))
    rc = iutil.execWithRedirect("/sbin/mkbootdisk",
				[ "/sbin/mkbootdisk",
				  "--noprompt",
				  "--device",
				  "/dev/" + floppyDevice,
				  kernelTag[1:] ],
				stdout = '/dev/tty5', stderr = '/dev/tty5',
				searchPath = 1, root = self.instPath)
    w.pop()

    if rc:
	import dispatch
	return dispatch.DISPATCH_BACK

