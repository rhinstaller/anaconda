
import types, os, sys, isys, select, string

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
		     searchPath = 0, root = '/'):
    stdin = getfd(stdin)
    stdout = getfd(stdout)
    stderr = getfd(stderr)

    if not os.access (command, os.X_OK):
        raise RuntimeError, command + " can not be run"

    childpid = os.fork()
    if (not childpid):
        if (root != '/'): isys.chroot (root)

	if stdin != 0:
	    os.dup2(stdin, 0)
	    os.close(stdin)
	if stdout != 1:
	    os.dup2(stdout, 1)
	    os.close(stdout)
	if stderr != 2:
	    os.dup2(stderr, 2)
	    os.close(stderr)

	if (searchPath):
	    os.execvp(command, argv)
	else:
	    os.execv(command, argv)

	sys.exit(1)
    (pid, status) = os.waitpid(childpid, 0)

    return status

def execWithCapture(command, argv, searchPath = 0, root = '/', stdin = 0):

    if not os.access (command, os.X_OK):
        raise RuntimeError, command + " can not be run"
    
    (read, write) = os.pipe()

    childpid = os.fork()
    if (not childpid):
        if (root != '/'): isys.chroot (root)
	os.dup2(write, 1)

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

    os.waitpid(childpid, 0)

    return rc

def copyFile(source, to):
    f = os.open(source, os.O_RDONLY)
    t = os.open(to, os.O_RDWR | os.O_TRUNC | os.O_CREAT)

    count = os.read(f, 16384)
    while (count):
	os.write(t, count)
	count = os.read(f, 16384)
	
    os.close(f)
    os.close(t)

def memInstalled():
    f = open("/proc/meminfo", "r")
    mem = f.readlines()[1]
    del f

    fields = string.split(mem)
    return int(fields[1]) / 1024
