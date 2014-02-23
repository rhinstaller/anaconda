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
#include <dirent.h>
#include <errno.h>
#define u32 __u32
#include <fcntl.h>
/* Need to tell loop.h what the actual dev_t type is. */
#undef dev_t
#if defined(__alpha)
#define dev_t unsigned int
#else
#if defined(__x86_64__)
#define dev_t unsigned long
#else
#define dev_t unsigned short
#endif
#endif
#include <linux/loop.h>
#undef dev_t
#define dev_t dev_t
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/sysmacros.h>
#include <sys/time.h>
#include <sys/utsname.h>
#include <sys/vfs.h>
#include <unistd.h>
#include <sys/vt.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <linux/fb.h>
#include <libintl.h>
#include <libgen.h>
#include <linux/cdrom.h>
#include <linux/major.h>
#include <signal.h>
#include <execinfo.h>

#ifdef MAJOR_IN_MKDEV
#include <sys/mkdev.h>
#endif

#ifdef MAJOR_IN_SYSMACROS
#include <sys/sysmacros.h>
#endif

#ifndef CDROMEJECT
#define CDROMEJECT 0x5309
#endif

static PyObject * doisPseudoTTY(PyObject * s, PyObject * args);
static PyObject * doSync(PyObject * s, PyObject * args);
static PyObject * doSegvHandler(PyObject *s, PyObject *args);
static PyObject * doGetAnacondaVersion(PyObject * s, PyObject * args);
static PyObject * doSetSystemTime(PyObject *s, PyObject *args);

static PyMethodDef isysModuleMethods[] = {
    { "isPseudoTTY", (PyCFunction) doisPseudoTTY, METH_VARARGS, NULL},
    { "sync", (PyCFunction) doSync, METH_VARARGS, NULL},
    { "handleSegv", (PyCFunction) doSegvHandler, METH_VARARGS, NULL },
    { "getAnacondaVersion", (PyCFunction) doGetAnacondaVersion, METH_VARARGS, NULL },
    { "set_system_time", (PyCFunction) doSetSystemTime, METH_VARARGS, NULL},
    { NULL, NULL, 0, NULL }
} ;

#define BOOT_SIGNATURE	0xaa55	/* boot signature */
#define BOOT_SIG_OFFSET	510	/* boot signature offset */

/* cppcheck-suppress unusedFunction */
void init_isys(void) {
    Py_InitModule("_isys", isysModuleMethods);
}

static PyObject * doisPseudoTTY(PyObject * s, PyObject * args) {
    int fd;
    struct stat sb;

    if (!PyArg_ParseTuple(args, "i", &fd)) return NULL;
    fstat(fd, &sb);

    /* XXX close enough for now */
    return Py_BuildValue("i", ((major(sb.st_rdev) >= 136) && (major(sb.st_rdev) <= 143)));
}

static PyObject * doSync(PyObject * s, PyObject * args) {
    int fd;

    if (!PyArg_ParseTuple(args, "", &fd)) return NULL;
    sync();

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doSegvHandler(PyObject *s, PyObject *args) {
    void *array[20];
    size_t size;
    char **strings;
    size_t i;

    signal(SIGSEGV, SIG_DFL); /* back to default */
    
    size = backtrace (array, 20);
    strings = backtrace_symbols (array, size);
    
    printf ("Anaconda received SIGSEGV!.  Backtrace:\n");
    for (i = 0; i < size; i++)
        printf ("%s\n", strings[i]);
     
    free (strings);
    exit(1);
}

static PyObject * doGetAnacondaVersion(PyObject * s, PyObject * args) {
    return Py_BuildValue("s", VERSION_RELEASE);
}

static PyObject * doSetSystemTime(PyObject *s, PyObject  *args) {
    struct timeval tv;
    tv.tv_usec = 0;

    if (!PyArg_ParseTuple(args, "L", &(tv.tv_sec)))
        return NULL;

    if (settimeofday(&tv, NULL) != 0)
        PyErr_SetFromErrno(PyExc_SystemError);

    Py_INCREF(Py_None);
    return Py_None;
}


/* vim:set shiftwidth=4 softtabstop=4: */
