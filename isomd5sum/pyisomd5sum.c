#include <Python.h>
#include <stdio.h>

#include "libcheckisomd5.h"
#include "libimplantisomd5.h"

static PyObject * doCheckIsoMD5Sum(PyObject * s, PyObject * args);
static PyObject * doImplantIsoMD5Sum(PyObject * s, PyObject * args);

static PyMethodDef isomd5sumMethods[] = {
    { "checkisomd5sum", (PyCFunction) doCheckIsoMD5Sum, METH_VARARGS, NULL },
    { "implantisomd5sum", (PyCFunction) doImplantIsoMD5Sum, METH_VARARGS, NULL },
    { NULL }
} ;


static PyObject * doCheckIsoMD5Sum(PyObject * s, PyObject * args) {
    char *isofile;
    int rc;

    if (!PyArg_ParseTuple(args, "s", &isofile))
	return NULL;
 
    rc = mediaCheckFile(isofile, 1);

    return Py_BuildValue("i", rc);
}

static PyObject * doImplantIsoMD5Sum(PyObject * s, PyObject * args) {
    char *isofile, *errstr;
    int forceit, supported;
    int rc;

    if (!PyArg_ParseTuple(args, "sii", &isofile, &supported, &forceit))
	return NULL;

    rc = implantISOFile(isofile, supported, forceit, 1, &errstr);

    return Py_BuildValue("i", rc);
}


void initpyisomd5sum(void) {
    PyObject * m, * d;

    m = Py_InitModule("pyisomd5sum", isomd5sumMethods);
    d = PyModule_GetDict(m);
}
