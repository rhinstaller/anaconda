
import types, os, sys, isys

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

    childpid = os.fork()
    if (not childpid):
        isys.chroot (root)
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
    status = os.waitpid(childpid, 0)
    

