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

#include <sys/wait.h>
#include <unistd.h>

#include <Python.h>

static PyObject * edd_py_detect (PyObject * s, PyObject * args);

static PyMethodDef edd_module_methods[] = {
  { "detect",  (PyCFunction) edd_py_detect, METH_VARARGS, NULL },
  { NULL }
};

static PyObject *
edd_py_detect (PyObject * s, PyObject * args) {
  EDDCapability *ec;
  int device = 0x80;
  pid_t childpid;
  int status;

  if (!PyArg_ParseTuple(args, "|i", &device))
    return NULL;

  /* Run this probe as a child as it sometimes segv's in the vm stuff. 
     The child returns 1 if edd works, and 0 if it doesn't. */

  if (!(childpid = fork())) {
      if ((ec = edd_supported(device))) {
	free (ec);
	exit(1);
      }

      exit(0);
  }

  waitpid(childpid, &status, 0);

  if (WIFEXITED(status) && WEXITSTATUS(status))
    return Py_BuildValue ("i", 1);

  return Py_BuildValue ("i", 0);
}

void initedd (void) {
    Py_InitModule("edd", edd_module_methods);
}
