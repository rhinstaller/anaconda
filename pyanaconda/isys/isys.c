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

#include <stdio.h>
#include <sys/time.h>
#include <unistd.h>
#include <sys/types.h>
#include <signal.h>
#include <execinfo.h>
#include <stdlib.h>
#include <string.h>

static PyObject * doSync(PyObject * s, PyObject * args);
static PyObject * doSignalHandlers(PyObject *s, PyObject *args);
static PyObject * doSetSystemTime(PyObject *s, PyObject *args);

static PyMethodDef isysModuleMethods[] = {
    { "sync", (PyCFunction) doSync, METH_NOARGS, NULL},
    { "installSyncSignalHandlers", (PyCFunction) doSignalHandlers, METH_NOARGS, NULL},
    { "set_system_time", (PyCFunction) doSetSystemTime, METH_VARARGS, NULL},
    { NULL, NULL, 0, NULL }
} ;

/* cppcheck-suppress unusedFunction */
void init_isys(void) {
    Py_InitModule("_isys", isysModuleMethods);
}

static PyObject * doSync(PyObject * s, PyObject * args) {
    sync();

    Py_INCREF(Py_None);
    return Py_None;
}

static void sync_signal_handler(int signum) {
    void *array[20];
    size_t size;
    char **strings;
    size_t i;

    size = backtrace (array, 20);
    strings = backtrace_symbols (array, size);
    
    printf ("Anaconda received signal %d!.  Backtrace:\n", signum);
    for (i = 0; i < size; i++)
        printf ("%s\n", strings[i]);
     
    free (strings);
    exit(1);
}

static PyObject * doSignalHandlers(PyObject *s, PyObject *args) {
    /* Install a signal handler for all synchronous signals */
    struct sigaction sa;

    memset(&sa, 0, sizeof(struct sigaction));
    sa.sa_handler = sync_signal_handler;

    /* Use these flags to ensure that a crash within the signal handler will
     * just crash anaconda and not get stuck in a loop. RESETHAND resets the
     * handler to SIG_DFL when the handler is entered, so that further signals
     * will exit the program, and NODEFER ensures that the signal is not blocked
     * during the signal handler, so a SIGSEGV triggered by handling a SIGSEGV will
     * be processed and will use the default handler. The Linux kernel forces
     * both of these things during a signal handler crash, but this makes it
     * explicit.
     *
     * These flags also mean that a SIGSEGV from a second thread could abort
     * the processing of a SIGSEGV from a first, but too bad.
     */
    sa.sa_flags = SA_RESETHAND | SA_NODEFER;

    if (sigaction(SIGILL, &sa, NULL) != 0) {
        return PyErr_SetFromErrno(PyExc_SystemError);
    }

    if (sigaction(SIGFPE, &sa, NULL) != 0) {
        return PyErr_SetFromErrno(PyExc_SystemError);
    }

    if (sigaction(SIGSEGV, &sa, NULL) != 0) {
        return PyErr_SetFromErrno(PyExc_SystemError);
    }

    Py_INCREF(Py_None);
    return Py_None;
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
