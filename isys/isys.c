#include <stdio.h>
#include <dirent.h>
#include <errno.h>
#include <linux/ext2_fs.h>
#include <ext2fs/ext2fs.h>
#include <fcntl.h>
#include <popt.h>
/* Need to tell loop.h what the actual dev_t type is. */
#undef dev_t
#if defined(__alpha) || (defined(__sparc__) && defined(__arch64__))
#define dev_t unsigned int
#else
#define dev_t unsigned short
#endif
#include <linux/loop.h>
#undef dev_t
#define dev_t dev_t
#include <sys/ioctl.h>
#include <sys/mount.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <sys/time.h>
#include <sys/vfs.h>
#include <unistd.h>
#include <resolv.h>
#include <pump.h>
#include <scsi/scsi.h>
#include <scsi/scsi_ioctl.h>
#include <sys/vt.h>

#include "Python.h"

#include "md-int.h"
#include "imount.h"
#include "isys.h"
#include "probe.h"
#include "smp.h"
#include "lang.h"
#include "../balkan/byteswap.h"

#ifndef CDROMEJECT
#define CDROMEJECT 0x5309
#endif

long long llseek(int fd, long long offset, int whence);

/* FIXME: this is such a hack -- moduleInfoList ought to be a proper object */
moduleInfoSet modInfoList = NULL;

static PyObject * doFindModInfo(PyObject * s, PyObject * args);
static PyObject * doGetOpt(PyObject * s, PyObject * args);
/*static PyObject * doInsmod(PyObject * s, PyObject * args);
static PyObject * doRmmod(PyObject * s, PyObject * args);*/
static PyObject * doMount(PyObject * s, PyObject * args);
static PyObject * doReadModInfo(PyObject * s, PyObject * args);
static PyObject * doUMount(PyObject * s, PyObject * args);
static PyObject * getModuleList(PyObject * s, PyObject * args);
static PyObject * makeDevInode(PyObject * s, PyObject * args);
static PyObject * smpAvailable(PyObject * s, PyObject * args);
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
static PyObject * doLoChangeFd(PyObject * s, PyObject * args);
static PyObject * doDdFile(PyObject * s, PyObject * args);
static PyObject * doGetRaidSuperblock(PyObject * s, PyObject * args);
static PyObject * doDevSpaceFree(PyObject * s, PyObject * args);
static PyObject * doRaidStart(PyObject * s, PyObject * args);
static PyObject * doRaidStop(PyObject * s, PyObject * args);
static PyObject * doConfigNetDevice(PyObject * s, PyObject * args);
static PyObject * doPumpNetDevice(PyObject * s, PyObject * args);
static PyObject * doResetResolv(PyObject * s, PyObject * args);
static PyObject * doSetResolvRetry(PyObject * s, PyObject * args);
static PyObject * doLoadFont(PyObject * s, PyObject * args);
static PyObject * doLoadKeymap(PyObject * s, PyObject * args);
static PyObject * doReadE2fsLabel(PyObject * s, PyObject * args);
static PyObject * doExt2Dirty(PyObject * s, PyObject * args);
static PyObject * doIsScsiRemovable(PyObject * s, PyObject * args);
static PyObject * doIsIdeRemovable(PyObject * s, PyObject * args);
static PyObject * doEjectCdrom(PyObject * s, PyObject * args);
static PyObject * doVtActivate(PyObject * s, PyObject * args);
static PyObject * doisPsudoTTY(PyObject * s, PyObject * args);
static PyObject * doSync(PyObject * s, PyObject * args);
static PyObject * doisIsoImage(PyObject * s, PyObject * args);

static PyMethodDef isysModuleMethods[] = {
    { "ejectcdrom", (PyCFunction) doEjectCdrom, METH_VARARGS, NULL },
    { "e2dirty", (PyCFunction) doExt2Dirty, METH_VARARGS, NULL },
    { "e2fslabel", (PyCFunction) doReadE2fsLabel, METH_VARARGS, NULL },
    { "devSpaceFree", (PyCFunction) doDevSpaceFree, METH_VARARGS, NULL },
    { "raidstop", (PyCFunction) doRaidStop, METH_VARARGS, NULL },
    { "raidstart", (PyCFunction) doRaidStart, METH_VARARGS, NULL },
    { "getraidsb", (PyCFunction) doGetRaidSuperblock, METH_VARARGS, NULL },
    { "lochangefd", (PyCFunction) doLoChangeFd, METH_VARARGS, NULL },
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
    { "ProbedList", (PyCFunction) createProbedList, METH_VARARGS, NULL }, 
    { "readmoduleinfo", (PyCFunction) doReadModInfo, METH_VARARGS, NULL },
/*
    { "rmmod", (PyCFunction) doRmmod, METH_VARARGS, NULL },
*/
    { "mount", (PyCFunction) doMount, METH_VARARGS, NULL },
    { "smpavailable", (PyCFunction) smpAvailable, METH_VARARGS, NULL },
    { "umount", (PyCFunction) doUMount, METH_VARARGS, NULL },
    { "confignetdevice", (PyCFunction) doConfigNetDevice, METH_VARARGS, NULL },
    { "pumpnetdevice", (PyCFunction) doPumpNetDevice, METH_VARARGS, NULL },
    { "chroot", (PyCFunction) doChroot, METH_VARARGS, NULL },
    { "checkBoot", (PyCFunction) doCheckBoot, METH_VARARGS, NULL },
    { "checkUFS", (PyCFunction) doCheckUFS, METH_VARARGS, NULL },
    { "swapon",  (PyCFunction) doSwapon, METH_VARARGS, NULL },
    { "swapoff",  (PyCFunction) doSwapoff, METH_VARARGS, NULL },
    { "fbconprobe", (PyCFunction) doFbconProbe, METH_VARARGS, NULL },
    { "resetresolv", (PyCFunction) doResetResolv, METH_VARARGS, NULL },
    { "setresretry", (PyCFunction) doSetResolvRetry, METH_VARARGS, NULL },
    { "loadFont", (PyCFunction) doLoadFont, METH_VARARGS, NULL },
    { "loadKeymap", (PyCFunction) doLoadKeymap, METH_VARARGS, NULL },
    { "isScsiRemovable", (PyCFunction) doIsScsiRemovable, METH_VARARGS, NULL},
    { "isIdeRemovable", (PyCFunction) doIsIdeRemovable, METH_VARARGS, NULL},
    { "vtActivate", (PyCFunction) doVtActivate, METH_VARARGS, NULL},
    { "isPsudoTTY", (PyCFunction) doisPsudoTTY, METH_VARARGS, NULL},
    { "sync", (PyCFunction) doSync, METH_VARARGS, NULL},
    { "isisoimage", (PyCFunction) doisIsoImage, METH_VARARGS, NULL},
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

    if (!modInfoList)
	modInfoList = isysNewModuleInfoSet();

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
	    sync();
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

/* XXX - msw */
#ifndef LOOP_CHANGE_FD
#define LOOP_CHANGE_FD	0x4C04
#endif

static PyObject * doLoChangeFd(PyObject * s, PyObject * args) {
    int loopfd;
    int targfd;

    if (!PyArg_ParseTuple(args, "ii", &loopfd, &targfd)) 
	return NULL;
    if (ioctl(loopfd, LOOP_CHANGE_FD, targfd)) {
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

    if (!modInfoList)
	modInfoList = isysNewModuleInfoSet();

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
    char * str;
    char * error;
    const char ** argv;
    char strBuf[3];

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

    ch = shortArgs;
    numOptions = 0;
    while (*ch) {
        options[numOptions].shortName = *ch++;
        options[numOptions].longName = NULL;
	options[numOptions].val = 0;
	options[numOptions].descrip = NULL;
	options[numOptions].argDescrip = NULL;
	options[numOptions].arg = NULL;
	if (*ch == ':') {
	    options[numOptions].argInfo = POPT_ARG_STRING;
	    ch++;
	} else {
	    options[numOptions].argInfo = POPT_ARG_NONE;
	}

	options[numOptions].val = numOptions + 1;

	numOptions++;
    }

    for (i = 0; i < PyList_Size(longArgs); i++) {
        options[numOptions].shortName = 0;
	options[numOptions].val = 0;
	options[numOptions].descrip = NULL;
	options[numOptions].argDescrip = NULL;
	options[numOptions].arg = NULL;

        strObject = PyList_GetItem(longArgs, i);
	str = PyString_AsString(strObject);
	if (!str) return NULL;

	if (str[strlen(str) - 1] == '=') {
	    str = strcpy(alloca(strlen(str) + 1), str);
	    str[strlen(str) - 1] = '\0';
	    options[numOptions].argInfo = POPT_ARG_STRING;
	} else {
	    options[numOptions].argInfo = POPT_ARG_NONE;
	}

	options[numOptions].val = numOptions + 1;
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
    retList = PyList_New(0);
    retArgs = PyList_New(0);

    while ((rc = poptGetNextOpt(optCon)) >= 0) {
	const char * argument;

	rc--;

	if (options[rc].argInfo == POPT_ARG_STRING)
	    argument = poptGetOptArg(optCon);
	else
	    argument = NULL;
	    
	if (options[rc].longName) {
	    str = alloca(strlen(options[rc].longName) + 3);
	    sprintf(str, "--%s", options[rc].longName);
	} else {
	    str = strBuf;
	    sprintf(str, "-%c", options[rc].shortName);
	}

	if (argument) {
	    argument = strcpy(alloca(strlen(argument) + 1), argument);
	    PyList_Append(retList, 
			    Py_BuildValue("(ss)", str, argument));
	} else {
	    PyList_Append(retList, Py_BuildValue("(ss)", str, ""));
	}
    }

    if (rc < -1) {
	i = strlen(poptBadOption(optCon, POPT_BADOPTION_NOALIAS)) +
	    strlen(poptStrerror(rc));

	error = alloca(i) + 50;

	sprintf(error, "bad argument %s: %s\n", 
		poptBadOption(optCon, POPT_BADOPTION_NOALIAS), 
		poptStrerror(rc));

	PyErr_SetString(PyExc_TypeError, error);
	return NULL;
    }

    argv = (const char **) poptGetArgs(optCon);
    for (i = 0; argv && argv[i]; i++) {
	PyList_Append(retArgs, PyString_FromString(argv[i]));
    }

    poptFreeContext(optCon);

    return Py_BuildValue("(OO)", retList, retArgs);
}

static PyObject * doReadModInfo(PyObject * s, PyObject * args) {
    char * fn;

    if (!PyArg_ParseTuple(args, "s", &fn)) return NULL;

    if (!modInfoList)
	modInfoList = isysNewModuleInfoSet();

    if (isysReadModuleInfo(fn, modInfoList, NULL)) {
	PyErr_SetFromErrno(PyExc_IOError);
	return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
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
    int readOnly;

    if (!PyArg_ParseTuple(args, "sssi", &fs, &device, &mntpoint,
			  &readOnly)) return NULL;

    rc = doPwMount(device, mntpoint, fs, readOnly, 0, NULL, NULL);
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

int swapoff(const char * path);
int swapon(const char * path, int priorty);

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
    Py_InitModule("_isys", isysModuleMethods);
}

static PyObject * doConfigNetDevice(PyObject * s, PyObject * args) {
    char * dev, * ip, * netmask;
    char * gateway;
    struct pumpNetIntf device;
    typedef int int32;
    
    if (!PyArg_ParseTuple(args, "ssss", &dev, &ip, &netmask, &gateway)) 
	return NULL;

    memset(&device,'\0',sizeof(struct pumpNetIntf));
    strncpy(device.device, dev, sizeof(device.device) - 1);
    device.ip.s_addr = inet_addr(ip);
    device.netmask.s_addr = inet_addr(netmask);

    *((int32 *) &device.broadcast) = (*((int32 *) &device.ip) & 
		       *((int32 *) &device.netmask)) | 
		       ~(*((int32 *) &device.netmask));

    *((int32 *) &device.network) = 
	    *((int32 *) &device.ip) & *((int32 *) &device.netmask);

    device.set = PUMP_INTFINFO_HAS_IP | PUMP_INTFINFO_HAS_NETMASK |
		 PUMP_INTFINFO_HAS_BROADCAST | PUMP_INTFINFO_HAS_NETWORK;
    
    if (pumpSetupInterface(&device)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    if (strlen(gateway)) {
	device.gateway.s_addr = inet_addr(gateway);
	if (pumpSetupDefaultGateway(&device.gateway)) {
	    PyErr_SetFromErrno(PyExc_SystemError);
	    return NULL;
	}
    }

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doPumpNetDevice(PyObject * s, PyObject * args) {
    char * device;
    char * chptr;
    struct pumpNetIntf cfg;
    PyObject * rc;

    if (!PyArg_ParseTuple(args, "s", &device))
	return NULL;
	
    chptr = pumpDhcpRun(device, 0, 0, NULL, &cfg, NULL);
    if (chptr) {
	Py_INCREF(Py_None);
	return Py_None;
    }

    if (pumpSetupInterface(&cfg)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    if (pumpSetupDefaultGateway(&cfg.gateway)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    if (cfg.numDns)
	rc = PyString_FromString(inet_ntoa(cfg.dnsServers[0]));
    else
	rc = PyString_FromString("");

    return rc;
}

static PyObject * probedListGetAttr(probedListObject * o, char * name) {
    return Py_FindMethod(probedListObjectMethods, (PyObject * ) o, name);
}

static void probedListDealloc (probedListObject * o) {
    kdFree(&o->list);
}

static PyObject * probedListNet(probedListObject * o, PyObject * args) {
    if (!PyArg_ParseTuple(args, "")) return NULL;
    
    kdFindNetList(&o->list, 0);

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * probedListScsi(probedListObject * o, PyObject * args) {
    if (!PyArg_ParseTuple(args, "")) return NULL;

    kdFindScsiList(&o->list, 0);

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * probedListIde(probedListObject * o, PyObject * args) {
    if (!PyArg_ParseTuple(args, "")) return NULL;

    kdFindIdeList(&o->list, 0);

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
      case CLASS_UNSPEC:
      case CLASS_OTHER:
      case CLASS_SCSI:
      case CLASS_VIDEO:
      case CLASS_AUDIO:
      case CLASS_MOUSE:
      case CLASS_MODEM:
      case CLASS_FLOPPY:
	class = "floppy"; break;
      case CLASS_SCANNER:
      case CLASS_RAID:
      case CLASS_PRINTER:
      case CLASS_CAPTURE:
      case CLASS_KEYBOARD:
      case CLASS_MONITOR:
	break;
    }

    return Py_BuildValue("(sss)", class, po->list.known[item].name, model);
}

static PyObject * doPoptParse(PyObject * s, PyObject * args) {
    char * str;
    int argc, i;
    const char ** argv;
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
#ifdef __sparc__
	switch (fix.accel) {
	case FB_ACCEL_SUN_CREATOR:
	    var.bits_per_pixel = 24;
	    /* FALLTHROUGH */
	case FB_ACCEL_SUN_LEO:
	case FB_ACCEL_SUN_CGSIX:
	case FB_ACCEL_SUN_CG14:
	case FB_ACCEL_SUN_BWTWO:
	case FB_ACCEL_SUN_CGTHREE:
	case FB_ACCEL_SUN_TCX:
	    var.xres = var.xres_virtual;
	    var.yres = var.yres_virtual;
	    fix.smem_len = 0;
	    break;
	}
#endif
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
    case 24:
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

static PyObject * doLoadFont (PyObject * s, PyObject * args) {
    char * font;
    int ret;

    if (!PyArg_ParseTuple(args, "s", &font)) return NULL;

    ret = isysLoadFont (font);
    if (ret) {
	errno = -ret;
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }
    
    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doLoadKeymap (PyObject * s, PyObject * args) {
    char * keymap;
    int ret;

    if (!PyArg_ParseTuple(args, "s", &keymap)) return NULL;

    ret = isysLoadKeymap (keymap);
    if (ret) {
	errno = -ret;
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

    if (ioctl(fd, START_ARRAY, (unsigned long) sb.st_rdev)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doResetResolv(PyObject * s, PyObject * args) {
    if (!PyArg_ParseTuple(args, "")) return NULL;

    res_init();		/* reinit the resolver so DNS changes take affect */

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doSetResolvRetry(PyObject * s, PyObject * args) {
    int count;

    if (!PyArg_ParseTuple(args, "i", &count)) return NULL;

    _res.retry = count;

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doReadE2fsLabel(PyObject * s, PyObject * args) {
    char * device;
    ext2_filsys fsys;
    char buf[50];
    int rc;

    if (!PyArg_ParseTuple(args, "s", &device)) return NULL;

    rc = ext2fs_open(device, EXT2_FLAG_FORCE, 0, 0, unix_io_manager,
		     &fsys);
    if (rc) {
	Py_INCREF(Py_None);
	return Py_None;
    }

    memset(buf, 0, sizeof(buf));
    strncpy(buf, fsys->super->s_volume_name, 
	    sizeof(fsys->super->s_volume_name));

    ext2fs_close(fsys);

    return Py_BuildValue("s", buf); 
}

static PyObject * doExt2Dirty(PyObject * s, PyObject * args) {
    char * device;
    ext2_filsys fsys;
    int rc;
    int clean;

    if (!PyArg_ParseTuple(args, "s", &device)) return NULL;

    rc = ext2fs_open(device, EXT2_FLAG_FORCE, 0, 0, unix_io_manager,
		     &fsys);
    if (rc) {
	Py_INCREF(Py_None);
	return Py_None;
    }

    clean = fsys->super->s_state & EXT2_VALID_FS;

    ext2fs_close(fsys);

    return Py_BuildValue("i", !clean); 
}
/* doIsScsiRemovable()
   Returns:
    -1 on error
     0 if not removable
     0 if removable, but is aacraid driver (should be treated as not removable)
     1 if removable (not to be used by installer)
*/
static PyObject * doIsScsiRemovable(PyObject * s, PyObject * args) {
    char *path;
    int fd;
    int rc;
    typedef struct sdata_t {
	u_int32_t inlen;
	u_int32_t outlen;
	unsigned char cmd[128];
    } sdata;
    sdata inq;
    
    if (!PyArg_ParseTuple(args, "s", &path)) return NULL;

    memset (&inq, 0, sizeof (sdata));
    
    inq.inlen = 0;
    inq.outlen = 96;
    
    inq.cmd[0] = 0x12;          /* INQUIRY */
    inq.cmd[1] = 0x00;          /* lun=0, evpd=0 */
    inq.cmd[2] = 0x00;          /* page code = 0 */
    inq.cmd[3] = 0x00;          /* (reserved) */
    inq.cmd[4] = 96;            /* allocation length */
    inq.cmd[5] = 0x00;          /* control */
    
    fd = open (path, O_RDONLY);
    if (fd < 0) {
	if (errno == ENOMEDIUM)
	    return Py_BuildValue("i", 1); 
	else {
	    return Py_BuildValue("i", -1);
	}
    }

    /* look at byte 1, bit 7 for removable flag */
    if (!(rc = ioctl(fd, SCSI_IOCTL_SEND_COMMAND, &inq))) {
	if (inq.cmd[1] & (1 << 7)) {
	    /* XXX check the vendor, if it's DELL or HP it could be
	       an adaptec perc RAID (aacraid) device */
	    if ((!strncmp (inq.cmd + 8, "DELL", 4))
		|| (!strncmp (inq.cmd + 8, "HP", 2))) {
		rc = 0;
	    } else
		rc = 1;
	} else
	    rc = 0;
    } else {
/*	printf ("ioctl resulted in error %d\n", rc); */
	rc = -1;
    }

    close (fd);
    
    return Py_BuildValue("i", rc); 
}

static PyObject * doIsIdeRemovable(PyObject * s, PyObject * args) {
    char *path;
    char str[100];
    char devpath[250];
    char *t;
    int fd;
    int rc, i;
    DIR * dir;
    
    if (!PyArg_ParseTuple(args, "s", &path)) return NULL;

    if (access("/proc/ide", R_OK))
	return Py_BuildValue("i", -1); 

    if (!(dir = opendir("/proc/ide")))
	return Py_BuildValue("i", -1); 

    t = strrchr(path, '/');
    if (!t)
	return Py_BuildValue("i", -1); 

    /* set errno to 0, so we can tell when readdir() fails */
    snprintf(devpath, sizeof(devpath), "/proc/ide/%s/media", t+1);
    if ((fd = open(devpath, O_RDONLY)) >= 0) {
	i = read(fd, str, sizeof(str));
	close(fd);
	str[i - 1] = '\0';		/* chop off trailing \n */

	if (!strcmp(str, "floppy"))
	    rc = 1;
	else
	    rc = 0;
    } else {
	rc = -1;
    }

    return Py_BuildValue("i", rc); 
}

static PyObject * doEjectCdrom(PyObject * s, PyObject * args) {
    int fd;

    if (!PyArg_ParseTuple(args, "i", &fd)) return NULL;

    if (ioctl(fd, CDROMEJECT, 1)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doVtActivate(PyObject * s, PyObject * args) {
    int vtnum;

    if (!PyArg_ParseTuple(args, "i", &vtnum)) return NULL;

    if (ioctl(0, VT_ACTIVATE, vtnum)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doisPsudoTTY(PyObject * s, PyObject * args) {
    int fd;
    struct stat sb;

    if (!PyArg_ParseTuple(args, "i", &fd)) return NULL;
    fstat(fd, &sb);

    /* XXX close enough for now */
    return Py_BuildValue("i", (major(sb.st_rdev) == 3));
}

static PyObject * doSync(PyObject * s, PyObject * args) {
    int fd;

    if (!PyArg_ParseTuple(args, "", &fd)) return NULL;
    sync();

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doisIsoImage(PyObject * s, PyObject * args) {
    char * fn;
    int rc;

    if (!PyArg_ParseTuple(args, "s", &fn)) return NULL;
    /* ! returns proper true/false */
    rc = !fileIsIso(fn);
    
    return Py_BuildValue("i", rc);
}
int fileIsIso(const char * file);
