/*
 * pyedd.c - real mode bios library for discovering EDD capabilities of
 *           BIOS drives
 *
 * Matt Wilson <msw@redhat.com>
 *
 * Copyright 2000 Red Hat, Inc.
 *
 * This software may be freely redistributed under the terms of the GNU
 * library public license.
 *
 * You should have received a copy of the GNU Library Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 *
 */

#include "edd.h"

#include <Python.h>

static PyObject * edd_py_detect (PyObject * s, PyObject * args);

static PyMethodDef edd_module_methods[] = {
  { "detect",  (PyCFunction) edd_py_detect, METH_VARARGS, NULL },
  { NULL }
};

static PyObject *
edd_py_detect (PyObject * s, PyObject * args) {
  int device = 0x80;
  EDDCapability *ec;

  if (!PyArg_ParseTuple(args, "|i", &device))
    return NULL;

  if ((ec = edd_supported(device))) {
    free (ec);
    return Py_BuildValue ("i", 1);
  }
  return Py_BuildValue ("i", 0);
}

void initedd (void) {
    Py_InitModule("edd", edd_module_methods);
}
