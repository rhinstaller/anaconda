#include <errno.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <unistd.h>

#include "Python.h"

#include "imount.h"

static PyObject * doMount(PyObject * s, PyObject * args);

static PyMethodDef balkanModuleMethods[] = {
    { "mount", (PyCFunction) doMount, METH_VARARGS, NULL },
    { NULL }
} ;

static PyObject * doMount(PyObject * s, PyObject * args) {
    char * fs, * device, * mntpoint;

    if (!PyArg_ParseTuple(args, "sss", &fs, &device, &mntpoint)) return NULL;

    doPwMount(device, mntpoint, fs, 0, 0, NULL, NULL);

    Py_INCREF(Py_None);
    return Py_None;
}

void init_isys(void) {
    Py_InitModule("_isys", balkanModuleMethods);
}

static void emptyDestructor(PyObject * s) {
}
