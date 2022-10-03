/*
 * isys.c
 *
 * Copyright (C) 2007, 2008, 2009  Red Hat, Inc.  All rights reserved.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#include "config.h"
#include <Python.h>
#include <sys/time.h>
#include <stdlib.h>

static PyObject * doSetSystemTime(PyObject *s, PyObject *args);

static PyMethodDef isysModuleMethods[] = {
    { "set_system_time", doSetSystemTime, METH_VARARGS, "set system time"},
    { NULL, NULL, 0, NULL }
};

static struct PyModuleDef moduledef = {
        PyModuleDef_HEAD_INIT,
        "isys",
        "The Anaconda isys module",
        -1,
        isysModuleMethods,
};

PyMODINIT_FUNC
// cppcheck-suppress unusedFunction
PyInit__isys(void) {
    return PyModule_Create(&moduledef);
}

static PyObject * doSetSystemTime(PyObject *s, PyObject  *args) {
    struct timeval tv;
    tv.tv_usec = 0;

    if (!PyArg_ParseTuple(args, "L", &(tv.tv_sec)))
        return NULL;

    if (settimeofday(&tv, NULL) != 0)
        return PyErr_SetFromErrno(PyExc_SystemError);

    Py_INCREF(Py_None);
    return Py_None;
}


/* vim:set shiftwidth=4 softtabstop=4: */
