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
#include <ext2fs/ext2fs.h>
#include <fcntl.h>
/* Need to tell loop.h what the actual dev_t type is. */
#undef dev_t
#if defined(__alpha) || (defined(__sparc__) && defined(__arch64__))
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
#include <scsi/scsi.h>
#include <scsi/scsi_ioctl.h>
#include <sys/vt.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <arpa/inet.h>
#include <linux/fb.h>
#include <libintl.h>
#include <libgen.h>
#include <linux/cdrom.h>
#include <linux/major.h>
#include <linux/raid/md_u.h>
#include <linux/raid/md_p.h>
#include <signal.h>
#include <execinfo.h>

#include <blkid/blkid.h>

#include <X11/Xlib.h>
#include <X11/XKBlib.h>
#include <X11/keysym.h>

#include "iface.h"
#include "isys.h"
#include "imount.h"
#include "ethtool.h"
#include "lang.h"
#include "eddsupport.h"
#include "auditd.h"
#include "imount.h"
#include "log.h"

#ifndef CDROMEJECT
#define CDROMEJECT 0x5309
#endif

static PyObject * doMount(PyObject * s, PyObject * args);
static PyObject * doUMount(PyObject * s, PyObject * args);
static PyObject * doSwapon(PyObject * s, PyObject * args);
static PyObject * doSwapoff(PyObject * s, PyObject * args);
static PyObject * doLoSetup(PyObject * s, PyObject * args);
static PyObject * doUnLoSetup(PyObject * s, PyObject * args);
static PyObject * doLoChangeFd(PyObject * s, PyObject * args);
static PyObject * doWipeRaidSuperblock(PyObject * s, PyObject * args);
static PyObject * doGetRaidChunkSize(PyObject * s, PyObject * args);
static PyObject * doDevSpaceFree(PyObject * s, PyObject * args);
static PyObject * doResetResolv(PyObject * s, PyObject * args);
static PyObject * doLoadKeymap(PyObject * s, PyObject * args);
static PyObject * doExt2Dirty(PyObject * s, PyObject * args);
static PyObject * doExt2HasJournal(PyObject * s, PyObject * args);
static PyObject * doEjectCdrom(PyObject * s, PyObject * args);
static PyObject * doVtActivate(PyObject * s, PyObject * args);
static PyObject * doisPseudoTTY(PyObject * s, PyObject * args);
static PyObject * doisVioConsole(PyObject * s);
static PyObject * doSync(PyObject * s, PyObject * args);
static PyObject * doisIsoImage(PyObject * s, PyObject * args);
static PyObject * printObject(PyObject * s, PyObject * args);
static PyObject * py_bind_textdomain_codeset(PyObject * o, PyObject * args);
static PyObject * doSegvHandler(PyObject *s, PyObject *args);
static PyObject * doAuditDaemon(PyObject *s);
static PyObject * doPrefixToNetmask(PyObject *s, PyObject *args);
static PyObject * doGetBlkidData(PyObject * s, PyObject * args);
static PyObject * doIsCapsLockEnabled(PyObject * s, PyObject * args);
static PyObject * doGetLinkStatus(PyObject * s, PyObject * args);
static PyObject * doGetAnacondaVersion(PyObject * s, PyObject * args);
static PyObject * doInitLog(PyObject * s);

static PyMethodDef isysModuleMethods[] = {
    { "ejectcdrom", (PyCFunction) doEjectCdrom, METH_VARARGS, NULL },
    { "e2dirty", (PyCFunction) doExt2Dirty, METH_VARARGS, NULL },
    { "e2hasjournal", (PyCFunction) doExt2HasJournal, METH_VARARGS, NULL },
    { "devSpaceFree", (PyCFunction) doDevSpaceFree, METH_VARARGS, NULL },
    { "wiperaidsb", (PyCFunction) doWipeRaidSuperblock, METH_VARARGS, NULL },
    { "getraidchunk", (PyCFunction) doGetRaidChunkSize, METH_VARARGS, NULL },
    { "lochangefd", (PyCFunction) doLoChangeFd, METH_VARARGS, NULL },
    { "losetup", (PyCFunction) doLoSetup, METH_VARARGS, NULL },
    { "unlosetup", (PyCFunction) doUnLoSetup, METH_VARARGS, NULL },
    { "mount", (PyCFunction) doMount, METH_VARARGS, NULL },
    { "umount", (PyCFunction) doUMount, METH_VARARGS, NULL },
    { "resetresolv", (PyCFunction) doResetResolv, METH_VARARGS, NULL },
    { "swapon",  (PyCFunction) doSwapon, METH_VARARGS, NULL },
    { "swapoff",  (PyCFunction) doSwapoff, METH_VARARGS, NULL },
    { "loadKeymap", (PyCFunction) doLoadKeymap, METH_VARARGS, NULL },
    { "vtActivate", (PyCFunction) doVtActivate, METH_VARARGS, NULL},
    { "isPseudoTTY", (PyCFunction) doisPseudoTTY, METH_VARARGS, NULL},
    { "isVioConsole", (PyCFunction) doisVioConsole, METH_NOARGS, NULL},
    { "sync", (PyCFunction) doSync, METH_VARARGS, NULL},
    { "isisoimage", (PyCFunction) doisIsoImage, METH_VARARGS, NULL},
    { "printObject", (PyCFunction) printObject, METH_VARARGS, NULL},
    { "bind_textdomain_codeset", (PyCFunction) py_bind_textdomain_codeset, METH_VARARGS, NULL},
    { "handleSegv", (PyCFunction) doSegvHandler, METH_VARARGS, NULL },
    { "auditdaemon", (PyCFunction) doAuditDaemon, METH_NOARGS, NULL },
    { "prefix2netmask", (PyCFunction) doPrefixToNetmask, METH_VARARGS, NULL },
    { "getblkid", (PyCFunction) doGetBlkidData, METH_VARARGS, NULL },
    { "isCapsLockEnabled", (PyCFunction) doIsCapsLockEnabled, METH_VARARGS, NULL },
    { "getLinkStatus", (PyCFunction) doGetLinkStatus, METH_VARARGS, NULL },
    { "getAnacondaVersion", (PyCFunction) doGetAnacondaVersion, METH_VARARGS, NULL },
    { "initLog", (PyCFunction) doInitLog, METH_VARARGS, NULL },
    { NULL, NULL, 0, NULL }
} ;

static PyObject * doUnLoSetup(PyObject * s, PyObject * args) {
    int loopfd;

    if (!PyArg_ParseTuple(args, "i", &loopfd)) return NULL;
    if (ioctl(loopfd, LOOP_CLR_FD, 0)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}

/* XXX - msw */
#ifndef LOOP_CHANGE_FD
#define LOOP_CHANGE_FD	0x4C06
#endif

static PyObject * doLoChangeFd(PyObject * s, PyObject * args) {
    int loopfd;
    int targfd;

    if (!PyArg_ParseTuple(args, "ii", &loopfd, &targfd)) 
	return NULL;
    if (ioctl(loopfd, LOOP_CHANGE_FD, targfd)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doLoSetup(PyObject * s, PyObject * args) {
    int loopfd;
    int targfd;
    struct loop_info loopInfo;
    char * loopName;

    if (!PyArg_ParseTuple(args, "iis", &loopfd, &targfd, &loopName)) 
	return NULL;
    if (ioctl(loopfd, LOOP_SET_FD, targfd)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    memset(&loopInfo, 0, sizeof(loopInfo));
    strncpy(loopInfo.lo_name, basename(loopName), 63);

    if (ioctl(loopfd, LOOP_SET_STATUS, &loopInfo)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doUMount(PyObject * s, PyObject * args) {
    char *err = NULL, *mntpoint = NULL;
    int rc;

    if (!PyArg_ParseTuple(args, "s", &mntpoint)) {
        return NULL;
    }

    rc = doPwUmount(mntpoint, &err);
    if (rc == IMOUNT_ERR_ERRNO) {
        PyErr_SetFromErrno(PyExc_SystemError);
    } else if (rc) {
        PyObject *tuple = PyTuple_New(2);

        PyTuple_SetItem(tuple, 0, PyInt_FromLong(rc));

        if (err == NULL) {
            Py_INCREF(Py_None);
            PyTuple_SetItem(tuple, 1, Py_None);
        } else {
            PyTuple_SetItem(tuple, 1, PyString_FromString(err));
        }

        PyErr_SetObject(PyExc_SystemError, tuple);
    }

    if (rc) {
        return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doMount(PyObject * s, PyObject * args) {
    char *err = NULL, *fs, *device, *mntpoint, *flags = NULL;
    int rc;

    if (!PyArg_ParseTuple(args, "sss|z", &fs, &device, &mntpoint,
			  &flags)) return NULL;

    rc = doPwMount(device, mntpoint, fs, flags, &err);
    if (rc == IMOUNT_ERR_ERRNO)
	PyErr_SetFromErrno(PyExc_SystemError);
    else if (rc) {
        PyObject *tuple = PyTuple_New(2);

        PyTuple_SetItem(tuple, 0, PyInt_FromLong(rc));

        if (err == NULL) {
            Py_INCREF(Py_None);
            PyTuple_SetItem(tuple, 1, Py_None);
        } else {
            PyTuple_SetItem(tuple, 1, PyString_FromString(err));
        }

        PyErr_SetObject(PyExc_SystemError, tuple);
    }

    if (rc) return NULL;

    Py_INCREF(Py_None);
    return Py_None;
}

#define BOOT_SIGNATURE	0xaa55	/* boot signature */
#define BOOT_SIG_OFFSET	510	/* boot signature offset */

int swapoff(const char * path);
int swapon(const char * path, int priorty);

static PyObject * doSwapoff (PyObject * s, PyObject * args) {
    char * path;

    if (!PyArg_ParseTuple(args, "s", &path)) return NULL;

    if (swapoff (path)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }
    
    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doSwapon (PyObject * s, PyObject * args) {
    char * path;

    if (!PyArg_ParseTuple(args, "s", &path)) return NULL;

    if (swapon (path, 0)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }
    
    Py_INCREF(Py_None);
    return Py_None;
}

void init_isys(void) {
    PyObject * m, * d;

    m = Py_InitModule("_isys", isysModuleMethods);
    d = PyModule_GetDict(m);

    PyDict_SetItemString(d, "MIN_RAM", PyInt_FromLong(MIN_RAM));
    PyDict_SetItemString(d, "MIN_GUI_RAM", PyInt_FromLong(MIN_GUI_RAM));
    PyDict_SetItemString(d, "EARLY_SWAP_RAM", PyInt_FromLong(EARLY_SWAP_RAM));
}

static PyObject * doPrefixToNetmask (PyObject * s, PyObject * args) {
    int prefix = 0;
    struct in_addr *mask = NULL;
    char dst[INET_ADDRSTRLEN+1];

    if (!PyArg_ParseTuple(args, "i", &prefix))
        return NULL;

    if ((mask = iface_prefix2netmask(prefix)) == NULL)
        return NULL;

    if (inet_ntop(AF_INET, mask, dst, INET_ADDRSTRLEN) == NULL)
        return NULL;

    return Py_BuildValue("s", dst);
}

static PyObject * doResetResolv(PyObject * s, PyObject * args) {
    if (!PyArg_ParseTuple(args, "")) {
        return NULL;
    }

    /* reinit the resolver so DNS changes take affect */
    res_init();

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doWipeRaidSuperblock(PyObject * s, PyObject * args) {
    int fd;
    unsigned long size;
    struct mdp_super_t * sb;

    if (!PyArg_ParseTuple(args, "i", &fd)) return NULL;

    if (ioctl(fd, BLKGETSIZE, &size)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    /* put the size in 1k blocks */
    size >>= 1;

    if (lseek64(fd, ((off64_t) 512) * (off64_t) MD_NEW_SIZE_SECTORS(size), SEEK_SET) < 0) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    } 

    sb = malloc(sizeof(mdp_super_t));
    sb = memset(sb, '\0', sizeof(mdp_super_t));

    if (write(fd, sb, sizeof(sb)) != sizeof(sb)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    return Py_None;
}

static PyObject * doGetRaidChunkSize(PyObject * s, PyObject * args) {
    int fd;
    unsigned long size;
    mdp_super_t sb;

    if (!PyArg_ParseTuple(args, "i", &fd)) return NULL;

    if (ioctl(fd, BLKGETSIZE, &size)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    /* put the size in 1k blocks */
    size >>= 1;

    if (lseek64(fd, ((off64_t) 512) * (off64_t) MD_NEW_SIZE_SECTORS(size), SEEK_SET) < 0) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    } 

    if (read(fd, &sb, sizeof(sb)) != sizeof(sb)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    if (sb.md_magic != MD_SB_MAGIC) {
	PyErr_SetString(PyExc_ValueError, "bad md magic on device");
	return NULL;
    }

    return Py_BuildValue("i", sb.chunk_size / 1024);
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

static PyObject * doLoadKeymap (PyObject * s, PyObject * args) {
    char * keymap;
    int ret;

    if (!PyArg_ParseTuple(args, "s", &keymap)) return NULL;

    ret = isysLoadKeymap (keymap);
    if (ret) {
	errno = -ret;
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }
    
    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doExt2Dirty(PyObject * s, PyObject * args) {
    char * device;
    ext2_filsys fsys;
    int rc;
    int clean;

    if (!PyArg_ParseTuple(args, "s", &device)) return NULL;

    rc = ext2fs_open(device, EXT2_FLAG_FORCE, 0, 0, unix_io_manager,
		     &fsys);
    if (rc) {
	Py_INCREF(Py_None);
	return Py_None;
    }

    clean = fsys->super->s_state & EXT2_VALID_FS;

    ext2fs_close(fsys);

    return Py_BuildValue("i", !clean); 
}
static PyObject * doExt2HasJournal(PyObject * s, PyObject * args) {
    char * device;
    ext2_filsys fsys;
    int rc;
    int hasjournal;

    if (!PyArg_ParseTuple(args, "s", &device)) return NULL;
    rc = ext2fs_open(device, EXT2_FLAG_FORCE, 0, 0, unix_io_manager,
		     &fsys);
    if (rc) {
	Py_INCREF(Py_None);
	return Py_None;
    }

    hasjournal = fsys->super->s_feature_compat & EXT3_FEATURE_COMPAT_HAS_JOURNAL;

    ext2fs_close(fsys);

    return Py_BuildValue("i", hasjournal); 
}

static PyObject * doEjectCdrom(PyObject * s, PyObject * args) {
    int fd;

    if (!PyArg_ParseTuple(args, "i", &fd)) return NULL;

    /* Ask it to unlock the door and then eject the disc. There's really
     * nothing to do if unlocking doesn't work, so just eject without
     * worrying about it. -- pjones
     */
    ioctl(fd, CDROM_LOCKDOOR, 0);
    if (ioctl(fd, CDROMEJECT, 1)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doVtActivate(PyObject * s, PyObject * args) {
    int vtnum;

    if (!PyArg_ParseTuple(args, "i", &vtnum)) return NULL;

    if (ioctl(0, VT_ACTIVATE, vtnum)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
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

static PyObject * doGetBlkidData(PyObject * s, PyObject * args) {
    char * dev, * key;
    blkid_cache cache;
    blkid_dev bdev = NULL;
    blkid_tag_iterate titer;
    const char * type, * data;

    if (!PyArg_ParseTuple(args, "ss", &dev, &key)) return NULL;

    blkid_get_cache(&cache, NULL);

    bdev = blkid_get_dev(cache, dev, BLKID_DEV_NORMAL);
    if (bdev == NULL)
        goto out;
    titer = blkid_tag_iterate_begin(bdev);
    while (blkid_tag_next(titer, &type, &data) >= 0) {
        if (!strcmp(type, key)) {
            blkid_tag_iterate_end(titer);
            return Py_BuildValue("s", data);
        }
    }
    blkid_tag_iterate_end(titer);

 out:
    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doIsCapsLockEnabled(PyObject * s, PyObject * args) {
    Display *d = NULL;
    XkbStateRec state;

    if ((d = XOpenDisplay(NULL)) == NULL) {
        return NULL;
    }

    memset(&state, 0, sizeof(state));
    XkbGetState(d, XkbUseCoreKbd, &state);

    if (XCloseDisplay(d)) {
        return NULL;
    }

    return PyBool_FromLong(state.locked_mods & LockMask);
}

static PyObject * doGetLinkStatus(PyObject * s, PyObject * args) {
    char *dev = NULL;

    if (!PyArg_ParseTuple(args, "s", &dev)) {
        return NULL;
    }

    if (get_link_status(dev) == 1) {
        return PyBool_FromLong(1);
    }

    return PyBool_FromLong(0);
}

static PyObject * doGetAnacondaVersion(PyObject * s, PyObject * args) {
    return Py_BuildValue("s", VERSION);
}

static PyObject * doInitLog(PyObject * s) {
    openLog();
    Py_INCREF(Py_None);
    return Py_None;
}

/* vim:set shiftwidth=4 softtabstop=4: */
