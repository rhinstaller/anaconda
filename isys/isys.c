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
#include "smp.h"

static PyObject * doFindModInfo(PyObject * s, PyObject * args);
static PyObject * doInsmod(PyObject * s, PyObject * args);
static PyObject * doMount(PyObject * s, PyObject * args);
static PyObject * doReadModInfo(PyObject * s, PyObject * args);
static PyObject * doRmmod(PyObject * s, PyObject * args);
static PyObject * doUMount(PyObject * s, PyObject * args);
static PyObject * getModuleList(PyObject * s, PyObject * args);
static PyObject * makeDevInode(PyObject * s, PyObject * args);
static PyObject * pciProbe(PyObject * s, PyObject * args);
static PyObject * smpAvailable(PyObject * s, PyObject * args);
static PyObject * doConfigNetDevice(PyObject * s, PyObject * args);

static PyMethodDef isysModuleMethods[] = {
    { "findmoduleinfo", (PyCFunction) doFindModInfo, METH_VARARGS, NULL },
    { "insmod", (PyCFunction) doInsmod, METH_VARARGS, NULL },
    { "mkdevinode", (PyCFunction) makeDevInode, METH_VARARGS, NULL },
    { "modulelist", (PyCFunction) getModuleList, METH_VARARGS, NULL },
    { "pciprobe", (PyCFunction) pciProbe, METH_VARARGS, NULL },
    { "readmoduleinfo", (PyCFunction) doReadModInfo, METH_VARARGS, NULL },
    { "rmmod", (PyCFunction) doRmmod, METH_VARARGS, NULL },
    { "mount", (PyCFunction) doMount, METH_VARARGS, NULL },
    { "smpavailable", (PyCFunction) smpAvailable, METH_VARARGS, NULL },
    { "umount", (PyCFunction) doUMount, METH_VARARGS, NULL },
    { "confignetdevice", (PyCFunction) doConfigNetDevice, METH_VARARGS, NULL },
    { NULL }
} ;

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

    modules = isysGetModuleList(major);
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

    mi = isysFindModuleInfo(mod);
    if (!mi) {
	Py_INCREF(Py_None);
	return Py_None;
    }

    return buildModuleObject(mi);
}

static PyObject * doReadModInfo(PyObject * s, PyObject * args) {
    char * fn;

    if (!PyArg_ParseTuple(args, "s", &fn)) return NULL;

    if (isysReadModuleInfo(fn)) {
	PyErr_SetFromErrno(PyExc_IOError);
	return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * pciProbe(PyObject * s, PyObject * args) {
    char ** matches, ** item;
    PyObject * list;

    if (!PyArg_ParseTuple(args, "")) return NULL;

    /* may as well try <shrug> */
    probePciReadDrivers("isys/pci/pcitable");
    probePciReadDrivers("/etc/pcitable");

    matches = probePciDriverList();
    if (!matches) {
	Py_INCREF(Py_None);
	return Py_None;
    }

    list = PyList_New(0);
    for (item = matches; *item; item++) {
	PyList_Append(list, Py_BuildValue("s", *item));
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
