import isys
import os
import signal
from string import joinfields
import traceback
from cPickle import Pickler
from translate import _
import iutil

def handleException(todo, (type, value, tb)):
    list = traceback.format_exception (type, value, tb)
    text = joinfields (list, "")
    rc = todo.intf.exceptionWindow (_("Exception Occurred"), text)
    if rc == 1:
	todo.intf.__del__ ()
        print text
        import pdb
        pdb.post_mortem (tb)
        os.kill(os.getpid(), signal.SIGKILL)
    elif not rc:
	todo.intf.__del__ ()
        os.kill(os.getpid(), signal.SIGKILL)
            
    while 1:
	rc = todo.intf.dumpWindow()
	if rc:
	    todo.intf.__del__ ()
            os.kill(os.getpid(), signal.SIGKILL)

	device = todo.fdDevice
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

	out = open("/tmp/crash/anacdump.txt", "w")
	p = Pickler(out)

	out.write(text)

        trace = tb
        while trace.tb_next:
            trace = trace.tb_next
        frame = trace.tb_frame
        out.write ("\nLocal variables in innermost frame:\n")
        for (key, value) in frame.f_locals.items():
            out.write ("%s: %s\n" % (key, value))

	out.write("\nToDo object:\n")
        intf = todo.intf
	todo.intf = None
	todo.fstab = None
	todo.comps = None
	todo.hdList = None

	p.dump(todo)

	out.close()
	isys.umount("/tmp/crash")

	intf.__del__ ()
        os.kill(os.getpid(), signal.SIGKILL)
