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
#include <resolv.h>
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

#include <X11/Xlib.h>
#include <X11/XKBlib.h>
#include <X11/keysym.h>

#include "iface.h"
#include "isys.h"
#include "ethtool.h"
#include "lang.h"
#include "eddsupport.h"
#include "auditd.h"
#include "log.h"
#include "mem.h"

#ifndef CDROMEJECT
#define CDROMEJECT 0x5309
#endif

static PyObject * doDevSpaceFree(PyObject * s, PyObject * args);
static PyObject * doisPseudoTTY(PyObject * s, PyObject * args);
static PyObject * doisVioConsole(PyObject * s);
static PyObject * doSync(PyObject * s, PyObject * args);
static PyObject * doisIsoImage(PyObject * s, PyObject * args);
static PyObject * printObject(PyObject * s, PyObject * args);
static PyObject * py_bind_textdomain_codeset(PyObject * o, PyObject * args);
static PyObject * doSegvHandler(PyObject *s, PyObject *args);
static PyObject * doAuditDaemon(PyObject *s);
static PyObject * doIsCapsLockEnabled(PyObject * s, PyObject * args);
static PyObject * doGetAnacondaVersion(PyObject * s, PyObject * args);
static PyObject * doInitLog(PyObject * s);
static PyObject * doTotalMemory(PyObject * s);
static PyObject * doSetSystemTime(PyObject *s, PyObject *args);

static PyMethodDef isysModuleMethods[] = {
    { "devSpaceFree", (PyCFunction) doDevSpaceFree, METH_VARARGS, NULL },
    { "isPseudoTTY", (PyCFunction) doisPseudoTTY, METH_VARARGS, NULL},
    { "isVioConsole", (PyCFunction) doisVioConsole, METH_NOARGS, NULL},
    { "sync", (PyCFunction) doSync, METH_VARARGS, NULL},
    { "isisoimage", (PyCFunction) doisIsoImage, METH_VARARGS, NULL},
    { "printObject", (PyCFunction) printObject, METH_VARARGS, NULL},
    { "bind_textdomain_codeset", (PyCFunction) py_bind_textdomain_codeset, METH_VARARGS, NULL},
    { "handleSegv", (PyCFunction) doSegvHandler, METH_VARARGS, NULL },
    { "auditdaemon", (PyCFunction) doAuditDaemon, METH_NOARGS, NULL },
    { "isCapsLockEnabled", (PyCFunction) doIsCapsLockEnabled, METH_VARARGS, NULL },
    { "getAnacondaVersion", (PyCFunction) doGetAnacondaVersion, METH_VARARGS, NULL },
    { "initLog", (PyCFunction) doInitLog, METH_VARARGS, NULL },
    { "total_memory", (PyCFunction) doTotalMemory, METH_NOARGS, NULL },
    { "set_system_time", (PyCFunction) doSetSystemTime, METH_VARARGS, NULL},
    { NULL, NULL, 0, NULL }
} ;

#define BOOT_SIGNATURE	0xaa55	/* boot signature */
#define BOOT_SIG_OFFSET	510	/* boot signature offset */

void init_isys(void) {
    Py_InitModule("_isys", isysModuleMethods);
}

static int get_bits(unsigned long long v) {
    int  b = 0;
    
    if ( v & 0xffffffff00000000LLU ) { b += 32; v >>= 32; }
    if ( v & 0xffff0000LLU ) { b += 16; v >>= 16; }
    if ( v & 0xff00LLU ) { b += 8; v >>= 8; }
    if ( v & 0xf0LLU ) { b += 4; v >>= 4; }
    if ( v & 0xcLLU ) { b += 2; v >>= 2; }
    if ( v & 0x2LLU ) b++;
    
    return v ? b + 1 : b;
}

static PyObject * doDevSpaceFree(PyObject * s, PyObject * args) {
    char * path;
    struct statfs sb;
    unsigned long long size;

    if (!PyArg_ParseTuple(args, "s", &path)) return NULL;

    if (statfs(path, &sb)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    /* Calculate a saturated addition to prevent oveflow. */
    if ( get_bits(sb.f_bfree) + get_bits(sb.f_bsize) <= 64 )
        size = (unsigned long long)sb.f_bfree * sb.f_bsize;
    else
        size = ~0LLU;

    return PyLong_FromUnsignedLongLong(size>>20);
}

static PyObject * doisPseudoTTY(PyObject * s, PyObject * args) {
    int fd;
    struct stat sb;

    if (!PyArg_ParseTuple(args, "i", &fd)) return NULL;
    fstat(fd, &sb);

    /* XXX close enough for now */
    return Py_BuildValue("i", ((major(sb.st_rdev) >= 136) && (major(sb.st_rdev) <= 143)));
}

static PyObject * doisVioConsole(PyObject * s) {
    return Py_BuildValue("i", isVioConsole());
}

static PyObject * doSync(PyObject * s, PyObject * args) {
    int fd;

    if (!PyArg_ParseTuple(args, "", &fd)) return NULL;
    sync();

    Py_INCREF(Py_None);
    return Py_None;
}

int fileIsIso(const char * file);

static PyObject * doisIsoImage(PyObject * s, PyObject * args) {
    char * fn;
    int rc;

    if (!PyArg_ParseTuple(args, "s", &fn)) return NULL;

    rc = fileIsIso(fn);
    
    return Py_BuildValue("i", rc);
}

static PyObject * printObject (PyObject * o, PyObject * args) {
    PyObject * obj;
    char buf[256];

    if (!PyArg_ParseTuple(args, "O", &obj))
	return NULL;
    
    snprintf(buf, 256, "<%s object at %lx>", obj->ob_type->tp_name,
	     (long) obj);

    return PyString_FromString(buf);
}

static PyObject *
py_bind_textdomain_codeset(PyObject * o, PyObject * args) {
    char *domain, *codeset, *ret;
	
    if (!PyArg_ParseTuple(args, "ss", &domain, &codeset))
	return NULL;

    ret = bind_textdomain_codeset(domain, codeset);

    if (ret)
	return PyString_FromString(ret);

    PyErr_SetFromErrno(PyExc_SystemError);
    return NULL;
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

static PyObject * doAuditDaemon(PyObject *s) {
    audit_daemonize();
    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doIsCapsLockEnabled(PyObject * s, PyObject * args) {
    Display *d = NULL;
    XkbStateRec state;

    if ((d = XOpenDisplay(NULL)) == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "XOpenDisplay failed");
        return NULL;
    }

    memset(&state, 0, sizeof(state));
    XkbGetState(d, XkbUseCoreKbd, &state);

    if (XCloseDisplay(d)) {
        PyErr_SetString(PyExc_RuntimeError, "XCloseDisplay failed");
        return NULL;
    }

    return PyBool_FromLong(state.locked_mods & LockMask);
}

static PyObject * doGetAnacondaVersion(PyObject * s, PyObject * args) {
    return Py_BuildValue("s", VERSION);
}

static PyObject * doInitLog(PyObject * s) {
    openLog();
    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doTotalMemory(PyObject * s) {
    unsigned long long tm = totalMemory();
    return PyLong_FromUnsignedLongLong(tm);
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
