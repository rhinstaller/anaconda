#include <errno.h>
#include <fcntl.h>
#include <popt.h>
#include <sys/types.h>
#include <linux/loop.h>
#include <sys/ioctl.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/vfs.h>
#include <unistd.h>

#include "Python.h"

#include "md-int.h"
#include "imount.h"
#include "isys.h"
#include "probe.h"
#include "smp.h"
#include "../balkan/byteswap.h"

long long llseek(int fd, long long offset, int whence);

/* FIXME: this is such a hack -- moduleInfoList ought to be a proper object */
moduleInfoSet modInfoList;

static PyObject * doFindModInfo(PyObject * s, PyObject * args);
static PyObject * doGetOpt(PyObject * s, PyObject * args);
/*static PyObject * doInsmod(PyObject * s, PyObject * args);
static PyObject * doRmmod(PyObject * s, PyObject * args);*/
static PyObject * doMount(PyObject * s, PyObject * args);
static PyObject * doReadModInfo(PyObject * s, PyObject * args);
static PyObject * doUMount(PyObject * s, PyObject * args);
static PyObject * getModuleList(PyObject * s, PyObject * args);
static PyObject * makeDevInode(PyObject * s, PyObject * args);
static PyObject * doPciProbe(PyObject * s, PyObject * args);
static PyObject * smpAvailable(PyObject * s, PyObject * args);
#if 0
static PyObject * doConfigNetDevice(PyObject * s, PyObject * args);
#endif
static PyObject * createProbedList(PyObject * s, PyObject * args);
static PyObject * doChroot(PyObject * s, PyObject * args);
static PyObject * doCheckBoot(PyObject * s, PyObject * args);
static PyObject * doCheckUFS(PyObject * s, PyObject * args);
static PyObject * doSwapon(PyObject * s, PyObject * args);
static PyObject * doSwapoff(PyObject * s, PyObject * args);
static PyObject * doPoptParse(PyObject * s, PyObject * args);
static PyObject * doFbconProbe(PyObject * s, PyObject * args);
static PyObject * doLoSetup(PyObject * s, PyObject * args);
static PyObject * doUnLoSetup(PyObject * s, PyObject * args);
static PyObject * doDdFile(PyObject * s, PyObject * args);
static PyObject * doGetRaidSuperblock(PyObject * s, PyObject * args);
static PyObject * doDevSpaceFree(PyObject * s, PyObject * args);
static PyObject * doRaidStart(PyObject * s, PyObject * args);
static PyObject * doRaidStop(PyObject * s, PyObject * args);

static PyMethodDef isysModuleMethods[] = {
    { "devSpaceFree", (PyCFunction) doDevSpaceFree, METH_VARARGS, NULL },
    { "raidstop", (PyCFunction) doRaidStop, METH_VARARGS, NULL },
    { "raidstart", (PyCFunction) doRaidStart, METH_VARARGS, NULL },
    { "getraidsb", (PyCFunction) doGetRaidSuperblock, METH_VARARGS, NULL },
    { "losetup", (PyCFunction) doLoSetup, METH_VARARGS, NULL },
    { "unlosetup", (PyCFunction) doUnLoSetup, METH_VARARGS, NULL },
    { "ddfile", (PyCFunction) doDdFile, METH_VARARGS, NULL },
    { "findmoduleinfo", (PyCFunction) doFindModInfo, METH_VARARGS, NULL },
    { "getopt", (PyCFunction) doGetOpt, METH_VARARGS, NULL },
/*
    { "insmod", (PyCFunction) doInsmod, METH_VARARGS, NULL },
*/
    { "poptParseArgv", (PyCFunction) doPoptParse, METH_VARARGS, NULL },
    { "mkdevinode", (PyCFunction) makeDevInode, METH_VARARGS, NULL },
    { "modulelist", (PyCFunction) getModuleList, METH_VARARGS, NULL },
    { "pciprobe", (PyCFunction) doPciProbe, METH_VARARGS, NULL },
    { "ProbedList", (PyCFunction) createProbedList, METH_VARARGS, NULL }, 
    { "readmoduleinfo", (PyCFunction) doReadModInfo, METH_VARARGS, NULL },
/*
    { "rmmod", (PyCFunction) doRmmod, METH_VARARGS, NULL },
*/
    { "mount", (PyCFunction) doMount, METH_VARARGS, NULL },
    { "smpavailable", (PyCFunction) smpAvailable, METH_VARARGS, NULL },
    { "umount", (PyCFunction) doUMount, METH_VARARGS, NULL },
#if 0
    { "confignetdevice", (PyCFunction) doConfigNetDevice, METH_VARARGS, NULL },
#endif
    { "chroot", (PyCFunction) doChroot, METH_VARARGS, NULL },
    { "checkBoot", (PyCFunction) doCheckBoot, METH_VARARGS, NULL },
    { "checkUFS", (PyCFunction) doCheckUFS, METH_VARARGS, NULL },
    { "swapon",  (PyCFunction) doSwapon, METH_VARARGS, NULL },
    { "swapoff",  (PyCFunction) doSwapoff, METH_VARARGS, NULL },
    { "fbconprobe", (PyCFunction) doFbconProbe, METH_VARARGS, NULL },
    { NULL }
} ;

typedef struct {
    PyObject_HEAD;
    struct knownDevices list;
} probedListObject;

static PyObject * probedListGetAttr(probedListObject * o, char * name);
static void probedListDealloc (probedListObject * o);
static PyObject * probedListNet(probedListObject * s, PyObject * args);
static PyObject * probedListScsi(probedListObject * s, PyObject * args);
static PyObject * probedListIde(probedListObject * s, PyObject * args);
static int probedListLength(PyObject * o);
static PyObject * probedListSubscript(probedListObject * o, int item);

static PyMethodDef probedListObjectMethods[] = {
    { "updateNet", (PyCFunction) probedListNet, METH_VARARGS, NULL },
    { "updateScsi", (PyCFunction) probedListScsi, METH_VARARGS, NULL },
    { "updateIde", (PyCFunction) probedListIde, METH_VARARGS, NULL },
    { NULL },
};

static PySequenceMethods probedListAsSequence = {
	probedListLength,		    /* length */
	0,		     		    /* concat */
	0,				    /* repeat */
	(intargfunc) probedListSubscript,   /* item */
	0,			 	    /* slice */
	0,				    /* assign item */
	0,				    /* assign slice */
};

static PyTypeObject probedListType = {
	PyObject_HEAD_INIT(&PyType_Type)
	0,				/* ob_size */
	"ProbedList",			/* tp_name */
	sizeof(probedListObject),	/* tp_size */
	0,				/* tp_itemsize */
	(destructor) probedListDealloc,	/* tp_dealloc */
	0,				/* tp_print */
	(getattrfunc) probedListGetAttr,/* tp_getattr */
	0,				/* tp_setattr */
	0,				/* tp_compare */
	0,				/* tp_repr */
	0,				/* tp_as_number */
	&probedListAsSequence,		/* tp_as_sequence */
	0,				/* tp_as_mapping */
};

static PyObject * buildModuleObject(struct moduleInfo * mi) {
    PyObject * major, * minor, * result;
    PyObject * modArgs;
    int i;

    switch (mi->major) {
      case DRIVER_SCSI:
	major = Py_BuildValue("s", "scsi"); break;
      case DRIVER_NET:
	major = Py_BuildValue("s", "net"); break;
      case DRIVER_CDROM:
	major = Py_BuildValue("s", "cdrom"); break;
      default:
	Py_INCREF(Py_None); major = Py_None; break;
    }

    switch (mi->minor) {
      case DRIVER_MINOR_PLIP:
	minor = Py_BuildValue("s", "plip"); break;
      case DRIVER_MINOR_ETHERNET:
	minor = Py_BuildValue("s", "ethernet"); break;
      case DRIVER_MINOR_TR:
	minor = Py_BuildValue("s", "tr"); break;
      default:
	Py_INCREF(Py_None); minor = Py_None; break;
    }

    modArgs = PyList_New(0);
    for (i = 0; i < mi->numArgs; i++) {
	PyList_Append(modArgs, Py_BuildValue("(ss)", mi->args[i].arg,
					  mi->args[i].description));
    }

    result = Py_BuildValue("(sOOsO)", mi->moduleName, major, minor, 
			   mi->description, modArgs);

    Py_DECREF(major);
    Py_DECREF(minor);

    return result;
}

static PyObject * getModuleList(PyObject * s, PyObject * args) {
    struct moduleInfo * modules, * m;
    char * type;
    PyObject * list;
    enum driverMajor major;

    if (!PyArg_ParseTuple(args, "s", &type)) return NULL;

    if (!strcmp(type, "scsi"))
	major = DRIVER_SCSI;
    else if (!strcmp(type, "cdrom"))
	major = DRIVER_CDROM;
    else if (!strcmp(type, "net"))
	major = DRIVER_NET;
    else {
	PyErr_SetString(PyExc_TypeError, "unexpected driver major type");
	return NULL;
    }

    modules = isysGetModuleList(modInfoList, major);
    if (!modules) {
	Py_INCREF(Py_None);
	return Py_None;
    }

    list = PyList_New(0);
    for (m = modules; m->moduleName; m++) {
	PyList_Append(list, Py_BuildValue("O", buildModuleObject(m)));
    }

    return list;
    
}

static PyObject * makeDevInode(PyObject * s, PyObject * args) {
    char * devName, * where;

    if (!PyArg_ParseTuple(args, "ss", &devName, &where)) return NULL;

    switch (devMakeInode(devName, where)) {
      case -1:
	PyErr_SetString(PyExc_TypeError, "unknown device");
      case -2:
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}

#if 0
static PyObject * doRmmod(PyObject * s, PyObject * pyargs) {
    char * modName;

    if (!PyArg_ParseTuple(pyargs, "s", &modName)) return NULL;

    if (rmmod(modName)) {
	PyErr_SetString(PyExc_SystemError, "rmmod failed");
	return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doInsmod(PyObject * s, PyObject * pyargs) {
    char * modName;
    PyObject * args, * obj;
    int argCount;
    int i;
    char ** argv;

    if (!PyArg_ParseTuple(pyargs, "sO", &modName, &args)) return NULL;

    if (!(PyList_Check(args))) {
	PyErr_SetString(PyExc_TypeError, "argument list expected");
	return NULL;
    }

    argCount = PyList_Size(args);
    argv = alloca(sizeof(*args) * (argCount + 1));
    for (i = 0; i < argCount; i++) {
	obj = PyList_GetItem(args, i);
	if (!PyString_Check(obj)) {
	    PyErr_SetString(PyExc_TypeError, "argument list expected");
	    return NULL;
	}
	argv[i] = PyString_AsString(obj);
    }
    argv[i] = NULL;

    if (insmod(modName, argv)) {
	PyErr_SetString(PyExc_SystemError, "insmod failed");
	return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}
#endif

static PyObject * doDdFile(PyObject * s, PyObject * args) {
    int fd;
    int megs;
    char * ptr;
    int i;

    if (!PyArg_ParseTuple(args, "ii", &fd, &megs)) return NULL;

    ptr = calloc(1024 * 256, 1);

    while (megs--) {
	for (i = 0; i < 4; i++) {
	    if (write(fd, ptr, 1024 * 256) != 1024 * 256) {
		PyErr_SetFromErrno(PyExc_SystemError);
		free(ptr);
		return NULL;
	    }
	}
    }

    free(ptr);

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doUnLoSetup(PyObject * s, PyObject * args) {
    int loopfd;

    if (!PyArg_ParseTuple(args, "i", &loopfd)) return NULL;
    if (ioctl(loopfd, LOOP_CLR_FD, 0)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doLoSetup(PyObject * s, PyObject * args) {
    int loopfd;
    int targfd;
    struct loop_info loopInfo;
    char * loopName;

    if (!PyArg_ParseTuple(args, "iis", &loopfd, &targfd, &loopName)) 
	return NULL;
    if (ioctl(loopfd, LOOP_SET_FD, targfd)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    memset(&loopInfo, 0, sizeof(loopInfo));
    strcpy(loopInfo.lo_name, loopName);

    if (ioctl(loopfd, LOOP_SET_STATUS, &loopInfo)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doFindModInfo(PyObject * s, PyObject * args) {
    char * mod;
    struct moduleInfo * mi;

    if (!PyArg_ParseTuple(args, "s", &mod)) return NULL;

    mi = isysFindModuleInfo(modInfoList, mod);
    if (!mi) {
	Py_INCREF(Py_None);
	return Py_None;
    }

    return buildModuleObject(mi);
}

static PyObject * doGetOpt(PyObject * s, PyObject * pyargs) {
    PyObject * argList, * longArgs, * strObject;
    PyObject * retList, * retArgs;
    char * shortArgs;
    struct poptOption * options;
    int numOptions, i, rc;
    char * ch;
    poptContext optCon;
    char ** args;
    int * occurs;
    char * str;
    char * error;
    char ** argv;
    char strBuf[2];

    if (!PyArg_ParseTuple(pyargs, "OsO", &argList, &shortArgs, &longArgs)) 
	return NULL;

    if (!(PyList_Check(argList))) {
	PyErr_SetString(PyExc_TypeError, "list expected");
    }
    if (!(PyList_Check(longArgs))) {
	PyErr_SetString(PyExc_TypeError, "list expected");
    }

    numOptions = PyList_Size(longArgs);
    for (ch = shortArgs; *ch; ch++)
	if (*ch != ':') numOptions++;

    options = alloca(sizeof(*options) * (numOptions + 1));
    args = alloca(sizeof(*args) * numOptions);
    memset(args, 0, sizeof(*args) * numOptions);
    occurs = alloca(sizeof(*occurs) * numOptions);
    memset(occurs, 0, sizeof(*occurs) * numOptions);

    ch = shortArgs;
    numOptions = 0;
    while (*ch) {
        options[numOptions].shortName = *ch++;
        options[numOptions].longName = NULL;
	options[numOptions].val = 0;
	options[numOptions].descrip = NULL;
	options[numOptions].argDescrip = NULL;
	if (*ch == ':') {
	    options[numOptions].argInfo = POPT_ARG_STRING;
	    options[numOptions].arg = args + numOptions;
	    ch++;
	} else {
	    options[numOptions].argInfo = POPT_ARG_NONE;
	    options[numOptions].arg = occurs + numOptions;
	}

	numOptions++;
    }

    for (i = 0; i < PyList_Size(longArgs); i++) {
        options[numOptions].shortName = 0;
	options[numOptions].val = 0;
	options[numOptions].descrip = NULL;
	options[numOptions].argDescrip = NULL;

        strObject = PyList_GetItem(longArgs, i);
	str = PyString_AsString(strObject);
	if (!str) return NULL;

	if (str[strlen(str) - 1] == '=') {
	    str = strcpy(alloca(strlen(str) + 1), str);
	    str[strlen(str) - 1] = '\0';
	    options[numOptions].argInfo = POPT_ARG_STRING;
	    options[numOptions].arg = args + numOptions;
	} else {
	    options[numOptions].argInfo = POPT_ARG_NONE;
	    options[numOptions].arg = occurs + numOptions;
	}

	options[numOptions].longName = str;

	numOptions++;
    }

    memset(options + numOptions, 0, sizeof(*options));

    argv = alloca(sizeof(*argv) * (PyList_Size(argList) + 1));
    for (i = 0; i < PyList_Size(argList); i++) {
        strObject = PyList_GetItem(argList, i);
	str = PyString_AsString(strObject);
	if (!str) return NULL;

	argv[i] = str;
    }

    argv[i] = NULL;

    optCon = poptGetContext("", PyList_Size(argList), argv,
			    options, POPT_CONTEXT_KEEP_FIRST);

    if ((rc = poptGetNextOpt(optCon)) < -1) {
	i = strlen(poptBadOption(optCon, POPT_BADOPTION_NOALIAS)) +
	    strlen(poptStrerror(rc));

	error = alloca(i) + 50;

	sprintf(error, "bad argument %s: %s\n", 
		poptBadOption(optCon, POPT_BADOPTION_NOALIAS), 
		poptStrerror(rc));

	PyErr_SetString(PyExc_TypeError, error);
	return NULL;
    }

    retList = PyList_New(0);

    ch = shortArgs;
    numOptions = 0;
    while (*ch) {
	if (!occurs[numOptions] && !args[numOptions]) {
	    ch++;
	    if (*ch == ':') ch++;
	    numOptions++;
	    continue;
	}

	strBuf[0] = '-';
	strBuf[1] = *ch++;
	strBuf[2] = '\0';

	if (*ch == ':') ch++;

	if (args[numOptions]) 
	    PyList_Append(retList, Py_BuildValue("(ss)", strBuf, 
			  args[numOptions]));
	else
	    PyList_Append(retList, Py_BuildValue("(ss)", strBuf, ""));

	numOptions++;
    }

    for (i = 0; i < PyList_Size(longArgs); i++) {
	if (!occurs[numOptions] && !args[numOptions]) {
	    numOptions++;
	    continue;
	}

        strObject = PyList_GetItem(longArgs, i);
	str = alloca(strlen(PyString_AsString(strObject)) + 3);
	sprintf(str, "--%s", PyString_AsString(strObject));
	if (!str) return NULL;

	if (args[numOptions]) {
	    str = strcpy(alloca(strlen(str) + 1), str);
	    str[strlen(str) - 1] = '\0';
	    PyList_Append(retList, Py_BuildValue("(ss)", str,
			  args[numOptions]));
	} else {
	    PyList_Append(retList, Py_BuildValue("(ss)", str, ""));
	}

	numOptions++;
    }

    retArgs = PyList_New(0);
    argv = (char **) poptGetArgs(optCon);
    for (i = 0; argv && argv[i]; i++) {
	PyList_Append(retArgs, PyString_FromString(argv[i]));
    }

    poptFreeContext(optCon);

    return Py_BuildValue("(OO)", retList, retArgs);
}

static PyObject * doReadModInfo(PyObject * s, PyObject * args) {
    char * fn;

    if (!PyArg_ParseTuple(args, "s", &fn)) return NULL;

    if (isysReadModuleInfo(fn, modInfoList, NULL)) {
	PyErr_SetFromErrno(PyExc_IOError);
	return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doPciProbe(PyObject * s, PyObject * args) {
    struct device ** matches, ** item;
    PyObject * list;

    if (!PyArg_ParseTuple(args, "")) return NULL;

    matches = probeDevices(CLASS_UNSPEC,BUS_PCI|BUS_SBUS,PROBE_ALL);

    if (!matches) {
	Py_INCREF(Py_None);
	return Py_None;
    }

    list = PyList_New(0);
    for (item = matches; *item; item++) {
	PyList_Append(list, Py_BuildValue("s", (*item)->driver));
	freeDevice (*item);
    }

    free(matches);

    return list;
}

static PyObject * doUMount(PyObject * s, PyObject * args) {
    char * fs;

    if (!PyArg_ParseTuple(args, "s", &fs)) return NULL;

    if (umount(fs)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doMount(PyObject * s, PyObject * args) {
    char * fs, * device, * mntpoint;
    int rc;

    if (!PyArg_ParseTuple(args, "sss", &fs, &device, &mntpoint)) return NULL;

    rc = doPwMount(device, mntpoint, fs, 0, 0, NULL, NULL);
    if (rc == IMOUNT_ERR_ERRNO) 
	PyErr_SetFromErrno(PyExc_SystemError);
    else if (rc)
	PyErr_SetString(PyExc_SystemError, "mount failed");

    if (rc) return NULL;

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doChroot(PyObject * s, PyObject * args) {
    char * path;

    if (!PyArg_ParseTuple(args, "s", &path)) return NULL;

    if (chroot (path)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }
    Py_INCREF(Py_None);
    return Py_None;
}

#define BOOT_SIGNATURE	0xaa55	/* boot signature */
#define BOOT_SIG_OFFSET	510	/* boot signature offset */

static PyObject * doCheckBoot (PyObject * s, PyObject * args) {
    char * path;
    int fd, size;
    unsigned short magic;
    PyObject * ret;

    /* code from LILO */
    
    if (!PyArg_ParseTuple(args, "s", &path)) return NULL;

    if ((fd = open (path, O_RDONLY)) < 0) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    if (lseek(fd,(long) BOOT_SIG_OFFSET, 0) < 0) {
	close (fd);
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }
    
    if ((size = read(fd,(char *) &magic, 2)) != 2) {
	close (fd);
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    close (fd);
    
    return Py_BuildValue("i", magic == BOOT_SIGNATURE);
}

#define UFS_SUPER_MAGIC		0x00011954

static PyObject * doCheckUFS (PyObject * s, PyObject * args) {
    char * path;
    int fd, magic;
    
    if (!PyArg_ParseTuple(args, "s", &path)) return NULL;

    if ((fd = open (path, O_RDONLY)) < 0) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }
    
    return Py_BuildValue("i", (llseek(fd, (8192 + 0x55c), SEEK_SET) >= 0 &&
			       read(fd, &magic, 4) == 4 &&
			       (magic == UFS_SUPER_MAGIC ||
				swab32(magic) == UFS_SUPER_MAGIC)));
}

static PyObject * doSwapoff (PyObject * s, PyObject * args) {
    char * path;

    if (!PyArg_ParseTuple(args, "s", &path)) return NULL;

    if (swapoff (path)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }
    
    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doSwapon (PyObject * s, PyObject * args) {
    char * path;

    if (!PyArg_ParseTuple(args, "s", &path)) return NULL;

    if (swapon (path, 0)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }
    
    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * smpAvailable(PyObject * s, PyObject * args) {
    int result;

    if (!PyArg_ParseTuple(args, "")) return NULL;

    result = detectSMP();

    return Py_BuildValue("i", detectSMP());
}

void init_isys(void) {
    modInfoList = isysNewModuleInfoSet();

    Py_InitModule("_isys", isysModuleMethods);
}

static void emptyDestructor(PyObject * s) {
}

#if 0
static PyObject * doConfigNetDevice(PyObject * s, PyObject * args) {
    char * dev, * ip, * netmask, * broadcast, * network;
    int * isPtp, rc;
    
    if (!PyArg_ParseTuple(args, "sssssd", &dev, &ip, &netmask, &broadcast,
			  &network, &isPtp)) return NULL;

    strncpy(device.device, dev, sizeof(device.device) - 1);
    device.ip.s_addr = inet_addr(ip);
    device.netmask.s_addr = inet_addr(netmask);
    device.broadcast.s_addr = inet_addr(broadcast);
    device.network.s_addr = inet_addr(network);
    device.set = PUMP_INTFINFO_HAS_IP | PUMP_INTFINFO_HAS_NETMASK |
		 PUMP_INTFINFO_HAS_BROADCAST | PUMP_INTFINFO_HAS_NETWORK;
    
    if (pumpSetupInterface(&device)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}
#endif

static PyObject * probedListGetAttr(probedListObject * o, char * name) {
    return Py_FindMethod(probedListObjectMethods, (PyObject * ) o, name);
}

static void probedListDealloc (probedListObject * o) {
    kdFree(&o->list);
}

static PyObject * probedListNet(probedListObject * o, PyObject * args) {
    if (!PyArg_ParseTuple(args, "")) return NULL;
    
    kdFindNetList(&o->list);

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * probedListScsi(probedListObject * o, PyObject * args) {
    if (!PyArg_ParseTuple(args, "")) return NULL;

    kdFindScsiList(&o->list);

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * probedListIde(probedListObject * o, PyObject * args) {
    if (!PyArg_ParseTuple(args, "")) return NULL;

    kdFindIdeList(&o->list);

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * createProbedList(PyObject * s, PyObject * args) {
    probedListObject * o;

    o = (probedListObject *) PyObject_NEW(PyObject, &probedListType);
    o->list = kdInit();

    return (PyObject *) o;
}

static int probedListLength(PyObject * o) {
    return ((probedListObject *) o)->list.numKnown;
}

static PyObject *indexerr;

static PyObject * probedListSubscript(probedListObject * o, int item) {
    probedListObject * po = (probedListObject *) o;
    char * model = "";
    char * class;

    if (item > o->list.numKnown - 1) {
	indexerr = PyString_FromString("list index out of range");
	PyErr_SetObject(PyExc_IndexError, indexerr);
	return NULL;
    }
    if (po->list.known[item].model) model = po->list.known[item].model;

    switch (po->list.known[item].class) {
      case CLASS_CDROM:
	class = "cdrom"; break;
      case CLASS_HD:
	class = "disk"; break;
      case CLASS_TAPE:
	class = "tape"; break;
      case CLASS_NETWORK:
	class = "net"; break;
    }

    return Py_BuildValue("(sss)", class, po->list.known[item].name, model);
}

static PyObject * doPoptParse(PyObject * s, PyObject * args) {
    char * str;
    int argc, i;
    char ** argv;
    PyObject * list;

    if (!PyArg_ParseTuple(args, "s", &str)) return NULL;

    if (poptParseArgvString(str, &argc, &argv)) {
	PyErr_SetString(PyExc_ValueError, "bad string for parsing");
	return NULL;
    }

    list = PyList_New(argc);
    for (i = 0; i < argc; i++)
	PyList_SetItem(list, i, PyString_FromString(argv[i]));

    free(argv);

    return list;
}

#include <linux/fb.h>

static PyObject * doFbconProbe (PyObject * s, PyObject * args) {
    char * path;
    int fd, size;
    PyObject * ret;
    struct fb_fix_screeninfo fix;
    struct fb_var_screeninfo var;
    char vidres[1024], vidmode[40];
    int depth = 0;

    if (!PyArg_ParseTuple(args, "s", &path)) return NULL;
    
    if ((fd = open (path, O_RDONLY)) < 0) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    if (ioctl(fd, FBIOGET_FSCREENINFO, &fix) < 0) {
	close (fd);
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    vidres[0] = 0;    
    if (ioctl(fd, FBIOGET_VSCREENINFO, &var) >= 0 && var.pixclock) {
	int x[4], y[4], vtotal, laced = 0, dblscan = 0;
	char *p;
	double drate, hrate, vrate;
	depth = var.bits_per_pixel;
	sprintf(vidmode, "%dx%d", var.xres, var.yres);
	x[0] = var.xres;
	x[1] = x[0] + var.right_margin;
	x[2] = x[1] + var.hsync_len;
	x[3] = x[2] + var.left_margin;
	y[0] = var.yres;
	y[1] = y[0] + var.lower_margin;
	y[2] = y[1] + var.vsync_len;
	y[3] = y[2] + var.upper_margin;
	vtotal = y[3];
	drate = 1E12/var.pixclock;
	switch (var.vmode & FB_VMODE_MASK) {
	case FB_VMODE_INTERLACED: laced = 1; break;
	case FB_VMODE_DOUBLE: dblscan = 1; break;
	}
	if (dblscan) vtotal <<= 2;
	else if (!laced) vtotal <<= 1;
	hrate = drate / x[3];
	vrate = hrate / vtotal * 2;
	sprintf (vidres,
	    "Section \"Monitor\"\n"
	    "    Identifier  \"Probed Monitor\"\n"
	    "    VendorName  \"Unknown\"\n"
	    "    ModelName   \"Unknown\"\n"
	    "    HorizSync   %5.3f\n"
	    "    VertRefresh %5.3f\n"
	    "    ModeLine    \"%dx%d\" %5.3f %d %d %d %d %d %d %d %d",
	    hrate/1E3, vrate,
	    x[0], y[0],
	    drate/1E6+0.001,
	    x[0], x[1], x[2], x[3],
	    y[0], y[1], y[2], y[3]);
	if (laced) strcat (vidres, " Interlaced");
	if (dblscan) strcat (vidres, " DoubleScan");
	p = strchr (vidres, 0);
	sprintf (p, " %cHSync %cVSync",
		 (var.sync & FB_SYNC_HOR_HIGH_ACT) ? '+' : '-',
		 (var.sync & FB_SYNC_VERT_HIGH_ACT) ? '+' : '-');
	if (var.sync & FB_SYNC_COMP_HIGH_ACT)
	    strcat (vidres, " Composite");
	if (var.sync & FB_SYNC_BROADCAST)
	    strcat (vidres, " bcast");
	strcat (vidres, "\nEndSection\n");
    }

    close (fd);
    /* Allow 64K from VIDRAM to be taken for other purposes */
    size = fix.smem_len + 65536;
    /* And round down to some multiple of 256K */
    size = size & ~0x3ffff;
    /* And report in KB */
    size >>= 10;

    switch (depth) {
    case 8:
    case 16:
    case 32:
    	return Py_BuildValue("(iiss)", size, depth, vidmode, vidres);
    }
    return Py_BuildValue("(iiss)", size, 0, "", "");
}

static PyObject * doGetRaidSuperblock(PyObject * s, PyObject * args) {
    int fd;
    unsigned long size;
    struct md_superblock_s sb;

    if (!PyArg_ParseTuple(args, "i", &fd)) return NULL;

    if (ioctl(fd, BLKGETSIZE, &size)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    /* put the size in 1k blocks */
    size >>= 1;

    if (llseek(fd, ((long long) 1024) * MD_NEW_SIZE_BLOCKS(size), SEEK_SET) < 0) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    } 

    if (read(fd, &sb, sizeof(sb)) != sizeof(sb)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    if (sb.md_magic != MD_SB_MAGIC) {
	PyErr_SetString(PyExc_ValueError, "bad md magic on device");
	return NULL;
    }

    return Py_BuildValue("(iiiiiii)", sb.major_version, sb.minor_version,
			 sb.set_magic, sb.level, sb.nr_disks,
			 sb.raid_disks, sb.md_minor);
}

static PyObject * doDevSpaceFree(PyObject * s, PyObject * args) {
    char * path;
    struct statfs sb;

    if (!PyArg_ParseTuple(args, "s", &path)) return NULL;

    if (statfs(path, &sb)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    return Py_BuildValue("i", sb.f_bfree * (sb.f_bsize / 1024) / (1024));
}

static PyObject * doRaidStop(PyObject * s, PyObject * args) {
    int fd;

    if (!PyArg_ParseTuple(args, "i", &fd)) return NULL;

    if (ioctl(fd, STOP_ARRAY, 0)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doRaidStart(PyObject * s, PyObject * args) {
    int fd;
    char * dev;
    struct stat sb;

    if (!PyArg_ParseTuple(args, "is", &fd, &dev)) return NULL;

    if (stat(dev, &sb)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    if (ioctl(fd, START_ARRAY, sb.st_rdev)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}
