#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <unistd.h>

#include "Python.h"

#include "imount.h"

static PyObject * doMount(PyObject * s, PyObject * args);
static PyObject * doUMount(PyObject * s, PyObject * args);

static PyMethodDef balkanModuleMethods[] = {
    { "mount", (PyCFunction) doMount, METH_VARARGS, NULL },
    { "umount", (PyCFunction) doUMount, METH_VARARGS, NULL },
    { NULL }
} ;

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

void init_isys(void) {
    Py_InitModule("_isys", balkanModuleMethods);
}

static void emptyDestructor(PyObject * s) {
}
