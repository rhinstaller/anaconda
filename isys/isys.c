#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <unistd.h>

#include "Python.h"

#include "imount.h"
#include "inet.h"
#include "isys.h"
#include "pci/pciprobe.h"
#include "probe.h"
#include "smp.h"

/* FIXME: this is such a hack -- moduleInfoList ought to be a proper object */
moduleInfoSet modInfoList;

static PyObject * doFindModInfo(PyObject * s, PyObject * args);
static PyObject * doInsmod(PyObject * s, PyObject * args);
static PyObject * doMount(PyObject * s, PyObject * args);
static PyObject * doReadModInfo(PyObject * s, PyObject * args);
static PyObject * doRmmod(PyObject * s, PyObject * args);
static PyObject * doUMount(PyObject * s, PyObject * args);
static PyObject * getModuleList(PyObject * s, PyObject * args);
static PyObject * makeDevInode(PyObject * s, PyObject * args);
static PyObject * doPciProbe(PyObject * s, PyObject * args);
static PyObject * smpAvailable(PyObject * s, PyObject * args);
static PyObject * doConfigNetDevice(PyObject * s, PyObject * args);
static PyObject * createProbedList(PyObject * s, PyObject * args);

static PyMethodDef isysModuleMethods[] = {
    { "findmoduleinfo", (PyCFunction) doFindModInfo, METH_VARARGS, NULL },
    { "insmod", (PyCFunction) doInsmod, METH_VARARGS, NULL },
    { "mkdevinode", (PyCFunction) makeDevInode, METH_VARARGS, NULL },
    { "modulelist", (PyCFunction) getModuleList, METH_VARARGS, NULL },
    { "pciprobe", (PyCFunction) doPciProbe, METH_VARARGS, NULL },
    { "ProbedList", (PyCFunction) createProbedList, METH_VARARGS, NULL }, 
    { "readmoduleinfo", (PyCFunction) doReadModInfo, METH_VARARGS, NULL },
    { "rmmod", (PyCFunction) doRmmod, METH_VARARGS, NULL },
    { "mount", (PyCFunction) doMount, METH_VARARGS, NULL },
    { "smpavailable", (PyCFunction) smpAvailable, METH_VARARGS, NULL },
    { "umount", (PyCFunction) doUMount, METH_VARARGS, NULL },
    { "confignetdevice", (PyCFunction) doConfigNetDevice, METH_VARARGS, NULL },
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
	probedListLength,		/* length */
	0,				/* concat */
	0,				/* repeat */
	probedListSubscript,		/* item */
	0,				/* slice */
	0,				/* assign item */
	0,				/* assign slice */
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

static PyObject * doReadModInfo(PyObject * s, PyObject * args) {
    char * fn;

    if (!PyArg_ParseTuple(args, "s", &fn)) return NULL;

    if (isysReadModuleInfo(fn, modInfoList)) {
	PyErr_SetFromErrno(PyExc_IOError);
	return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doPciProbe(PyObject * s, PyObject * args) {
    struct pciDevice ** matches, ** item;
    PyObject * list;

    if (!PyArg_ParseTuple(args, "")) return NULL;

    /* may as well try <shrug> */
    probePciReadDrivers("isys/pci/pcitable");
    probePciReadDrivers("/etc/pcitable");

    matches = probePci(0, 1);
    if (!matches) {
	Py_INCREF(Py_None);
	return Py_None;
    }

    list = PyList_New(0);
    for (item = matches; *item; item++) {
	PyList_Append(list, Py_BuildValue("s", (*item)->driver));
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

static PyObject * doConfigNetDevice(PyObject * s, PyObject * args) {
    char * dev, * ip, * netmask, * broadcast, * network;
    int * isPtp, rc;
    struct intfInfo device;
    
    if (!PyArg_ParseTuple(args, "sssssd", &dev, &ip, &netmask, &broadcast,
			  &network, &isPtp)) return NULL;

    strncpy(device.device, dev, sizeof(device.device) - 1);
    device.ip.s_addr = inet_addr(ip);
    device.netmask.s_addr = inet_addr(netmask);
    device.broadcast.s_addr = inet_addr(broadcast);
    device.network.s_addr = inet_addr(network);
    device.isPtp = 0;
    device.isUp = 0;
    
    rc = configureNetDevice(&device);
    
    if (rc == INET_ERR_ERRNO) 
	PyErr_SetFromErrno(PyExc_SystemError);
    else if (rc)
	PyErr_SetString(PyExc_SystemError, "net configure failed");

    Py_INCREF(Py_None);
    return Py_None;
}

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
      case DEVICE_CDROM:
	class = "cdrom"; break;
      case DEVICE_DISK:
	class = "disk"; break;
      case DEVICE_NET:
	class = "net"; break;
    }

    return Py_BuildValue("(sss)", class, po->list.known[item].name, model);
}
