#include <Python.h>

#include <sys/shm.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <stdio.h>
#include <dirent.h>
#include <errno.h>
#define u32 __u32
#include <linux/ext2_fs.h>
#include <linux/ext3_fs.h>
#include <ext2fs/ext2fs.h>
#include <fcntl.h>
#include <popt.h>
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
#include <sys/mount.h>
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
#include <linux/fb.h>
#include <libintl.h>
#ifdef USESELINUX
#include <selinux/selinux.h>
#endif
#include <libgen.h>
#include <linux/major.h>
#include <linux/raid/md_u.h>
#include <linux/raid/md_p.h>
#include <signal.h>
#include <execinfo.h>

#include <libdhcp/ip_addr.h>
#include <libdhcp/pump.h>

#include "nl.h"
#include "imount.h"
#include "isys.h"
#include "net.h"
#include "smp.h"
#include "lang.h"
#include "wireless.h"
#include "eddsupport.h"
#include "auditd.h"

#ifndef CDROMEJECT
#define CDROMEJECT 0x5309
#endif

static PyObject * doGetOpt(PyObject * s, PyObject * args);
/*static PyObject * doInsmod(PyObject * s, PyObject * args);
static PyObject * doRmmod(PyObject * s, PyObject * args);*/
static PyObject * doMount(PyObject * s, PyObject * args);
static PyObject * doUMount(PyObject * s, PyObject * args);
static PyObject * makeDevInode(PyObject * s, PyObject * args);
static PyObject * smpAvailable(PyObject * s, PyObject * args);
static PyObject * htAvailable(PyObject * s, PyObject * args);
static PyObject * doCheckBoot(PyObject * s, PyObject * args);
static PyObject * doSwapon(PyObject * s, PyObject * args);
static PyObject * doSwapoff(PyObject * s, PyObject * args);
static PyObject * doFbconProbe(PyObject * s, PyObject * args);
static PyObject * doLoSetup(PyObject * s, PyObject * args);
static PyObject * doUnLoSetup(PyObject * s, PyObject * args);
static PyObject * doLoChangeFd(PyObject * s, PyObject * args);
static PyObject * doDdFile(PyObject * s, PyObject * args);
static PyObject * doWipeRaidSuperblock(PyObject * s, PyObject * args);
static PyObject * doGetRaidSuperblock(PyObject * s, PyObject * args);
static PyObject * doGetRaidChunkSize(PyObject * s, PyObject * args);
static PyObject * doDevSpaceFree(PyObject * s, PyObject * args);
static PyObject * doRaidStart(PyObject * s, PyObject * args);
static PyObject * doRaidStop(PyObject * s, PyObject * args);
static PyObject * doConfigNetDevice(PyObject * s, PyObject * args);
static PyObject * doDhcpNetDevice(PyObject * s, PyObject * args);
static PyObject * doResetResolv(PyObject * s, PyObject * args);
static PyObject * doSetResolvRetry(PyObject * s, PyObject * args);
static PyObject * doLoadFont(PyObject * s, PyObject * args);
static PyObject * doLoadKeymap(PyObject * s, PyObject * args);
static PyObject * doClobberExt2 (PyObject * s, PyObject * args);
static PyObject * doReadE2fsLabel(PyObject * s, PyObject * args);
static PyObject * doExt2Dirty(PyObject * s, PyObject * args);
static PyObject * doExt2HasJournal(PyObject * s, PyObject * args);
static PyObject * doEjectCdrom(PyObject * s, PyObject * args);
static PyObject * doVtActivate(PyObject * s, PyObject * args);
static PyObject * doisPsudoTTY(PyObject * s, PyObject * args);
static PyObject * doisVioConsole(PyObject * s);
static PyObject * doSync(PyObject * s, PyObject * args);
static PyObject * doisIsoImage(PyObject * s, PyObject * args);
static PyObject * getFramebufferInfo(PyObject * s, PyObject * args);
static PyObject * printObject(PyObject * s, PyObject * args);
static PyObject * py_bind_textdomain_codeset(PyObject * o, PyObject * args);
static PyObject * getLinkStatus(PyObject * s, PyObject * args);
static PyObject * py_getDasdPorts(PyObject * s, PyObject * args);
static PyObject * py_isUsableDasd(PyObject * s, PyObject * args);
static PyObject * py_isLdlDasd(PyObject * s, PyObject * args);
static PyObject * doGetMacAddress(PyObject * s, PyObject * args);
static PyObject * doGetIPAddress(PyObject * s, PyObject * args);
#ifdef USESELINUX
static PyObject * doResetFileContext(PyObject * s, PyObject * args);
#endif
static PyObject * isWireless(PyObject * s, PyObject * args);
static PyObject * doProbeBiosDisks(PyObject * s, PyObject * args);
static PyObject * doGetBiosDisk(PyObject * s, PyObject * args); 
static PyObject * doSegvHandler(PyObject *s, PyObject *args);
static PyObject * doAuditDaemon(PyObject *s);
static PyObject * doPrefixToNetmask(PyObject *s, PyObject *args);
static PyObject * doDeviceReadOnly(PyObject *s, PyObject *args);

static PyMethodDef isysModuleMethods[] = {
    { "ejectcdrom", (PyCFunction) doEjectCdrom, METH_VARARGS, NULL },
    { "e2dirty", (PyCFunction) doExt2Dirty, METH_VARARGS, NULL },
    { "e2hasjournal", (PyCFunction) doExt2HasJournal, METH_VARARGS, NULL },
    { "e2fslabel", (PyCFunction) doReadE2fsLabel, METH_VARARGS, NULL },
    { "e2fsclobber", (PyCFunction) doClobberExt2, METH_VARARGS, NULL },
    { "devSpaceFree", (PyCFunction) doDevSpaceFree, METH_VARARGS, NULL },
    { "raidstop", (PyCFunction) doRaidStop, METH_VARARGS, NULL },
    { "raidstart", (PyCFunction) doRaidStart, METH_VARARGS, NULL },
    { "getraidsb", (PyCFunction) doGetRaidSuperblock, METH_VARARGS, NULL },
    { "wiperaidsb", (PyCFunction) doWipeRaidSuperblock, METH_VARARGS, NULL },
    { "getraidchunk", (PyCFunction) doGetRaidChunkSize, METH_VARARGS, NULL },
    { "lochangefd", (PyCFunction) doLoChangeFd, METH_VARARGS, NULL },
    { "losetup", (PyCFunction) doLoSetup, METH_VARARGS, NULL },
    { "unlosetup", (PyCFunction) doUnLoSetup, METH_VARARGS, NULL },
    { "ddfile", (PyCFunction) doDdFile, METH_VARARGS, NULL },
    { "getopt", (PyCFunction) doGetOpt, METH_VARARGS, NULL },
    { "mkdevinode", (PyCFunction) makeDevInode, METH_VARARGS, NULL },
    { "mount", (PyCFunction) doMount, METH_VARARGS, NULL },
    { "smpavailable", (PyCFunction) smpAvailable, METH_VARARGS, NULL },
    { "htavailable", (PyCFunction) htAvailable, METH_VARARGS, NULL },
    { "umount", (PyCFunction) doUMount, METH_VARARGS, NULL },
    { "confignetdevice", (PyCFunction) doConfigNetDevice, METH_VARARGS, NULL },
    { "dhcpnetdevice", (PyCFunction) doDhcpNetDevice, METH_VARARGS, NULL },
    { "checkBoot", (PyCFunction) doCheckBoot, METH_VARARGS, NULL },
    { "swapon",  (PyCFunction) doSwapon, METH_VARARGS, NULL },
    { "swapoff",  (PyCFunction) doSwapoff, METH_VARARGS, NULL },
    { "fbconprobe", (PyCFunction) doFbconProbe, METH_VARARGS, NULL },
    { "resetresolv", (PyCFunction) doResetResolv, METH_VARARGS, NULL },
    { "setresretry", (PyCFunction) doSetResolvRetry, METH_VARARGS, NULL },
    { "loadFont", (PyCFunction) doLoadFont, METH_VARARGS, NULL },
    { "loadKeymap", (PyCFunction) doLoadKeymap, METH_VARARGS, NULL },
    { "vtActivate", (PyCFunction) doVtActivate, METH_VARARGS, NULL},
    { "isPsudoTTY", (PyCFunction) doisPsudoTTY, METH_VARARGS, NULL},
    { "isVioConsole", (PyCFunction) doisVioConsole, METH_NOARGS, NULL},
    { "sync", (PyCFunction) doSync, METH_VARARGS, NULL},
    { "isisoimage", (PyCFunction) doisIsoImage, METH_VARARGS, NULL},
    { "fbinfo", (PyCFunction) getFramebufferInfo, METH_VARARGS, NULL},
    { "printObject", (PyCFunction) printObject, METH_VARARGS, NULL},
    { "bind_textdomain_codeset", (PyCFunction) py_bind_textdomain_codeset, METH_VARARGS, NULL},
    { "getLinkStatus", (PyCFunction) getLinkStatus, METH_VARARGS, NULL },
    { "getDasdPorts", (PyCFunction) py_getDasdPorts, METH_VARARGS, NULL},
    { "isUsableDasd", (PyCFunction) py_isUsableDasd, METH_VARARGS, NULL},
    { "isLdlDasd", (PyCFunction) py_isLdlDasd, METH_VARARGS, NULL},
    { "getMacAddress", (PyCFunction) doGetMacAddress, METH_VARARGS, NULL},
    { "getIPAddress", (PyCFunction) doGetIPAddress, METH_VARARGS, NULL},
#ifdef USESELINUX
    { "resetFileContext", (PyCFunction) doResetFileContext, METH_VARARGS, NULL },
#endif
    { "isWireless", (PyCFunction) isWireless, METH_VARARGS, NULL },
    { "biosDiskProbe", (PyCFunction) doProbeBiosDisks, METH_VARARGS,NULL},
    { "getbiosdisk",(PyCFunction) doGetBiosDisk, METH_VARARGS,NULL},
    { "handleSegv", (PyCFunction) doSegvHandler, METH_VARARGS, NULL },
    { "auditdaemon", (PyCFunction) doAuditDaemon, METH_NOARGS, NULL },
    { "prefix2netmask", (PyCFunction) doPrefixToNetmask, METH_VARARGS, NULL },
    { "deviceIsReadOnly", (PyCFunction) doDeviceReadOnly, METH_VARARGS, NULL },
    { NULL, NULL, 0, NULL }
} ;

static PyObject * makeDevInode(PyObject * s, PyObject * args) {
    char * devName, * where;

    if (!PyArg_ParseTuple(args, "ss", &devName, &where)) return NULL;

    switch (devMakeInode(devName, where)) {
      case -1:
	PyErr_SetString(PyExc_TypeError, "unknown device");
      case -2:
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doDdFile(PyObject * s, PyObject * args) {
    int fd;
    int megs;
    char * ptr;
    int i;

    if (!PyArg_ParseTuple(args, "ii", &fd, &megs)) return NULL;

    ptr = calloc(1024 * 256, 1);

    while (megs--) {
	for (i = 0; i < 4; i++) {
	    if (write(fd, ptr, 1024 * 256) != 1024 * 256) {
		PyErr_SetFromErrno(PyExc_SystemError);
		free(ptr);
		return NULL;
	    }
	    sync();
	}
    }

    free(ptr);

    Py_INCREF(Py_None);
    return Py_None;
}

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

static PyObject * doGetOpt(PyObject * s, PyObject * pyargs) {
    PyObject * argList, * longArgs, * strObject;
    PyObject * retList, * retArgs;
    char * shortArgs;
    struct poptOption * options;
    int numOptions, i, rc;
    char * ch;
    poptContext optCon;
    char * str;
    char * error;
    const char ** argv;
    char strBuf[3];

    if (!PyArg_ParseTuple(pyargs, "OsO", &argList, &shortArgs, &longArgs)) 
	return NULL;

    if (!(PyList_Check(argList))) {
	PyErr_SetString(PyExc_TypeError, "list expected");
    }
    if (!(PyList_Check(longArgs))) {
	PyErr_SetString(PyExc_TypeError, "list expected");
    }

    numOptions = PyList_Size(longArgs);
    for (ch = shortArgs; *ch; ch++)
	if (*ch != ':') numOptions++;

    options = alloca(sizeof(*options) * (numOptions + 1));

    ch = shortArgs;
    numOptions = 0;
    while (*ch) {
        options[numOptions].shortName = *ch++;
        options[numOptions].longName = NULL;
	options[numOptions].val = 0;
	options[numOptions].descrip = NULL;
	options[numOptions].argDescrip = NULL;
	options[numOptions].arg = NULL;
	if (*ch == ':') {
	    options[numOptions].argInfo = POPT_ARG_STRING;
	    ch++;
	} else {
	    options[numOptions].argInfo = POPT_ARG_NONE;
	}

	options[numOptions].val = numOptions + 1;

	numOptions++;
    }

    for (i = 0; i < PyList_Size(longArgs); i++) {
        options[numOptions].shortName = 0;
	options[numOptions].val = 0;
	options[numOptions].descrip = NULL;
	options[numOptions].argDescrip = NULL;
	options[numOptions].arg = NULL;

        strObject = PyList_GetItem(longArgs, i);
	str = PyString_AsString(strObject);
	if (!str) return NULL;

	if (str[strlen(str) - 1] == '=') {
	    str = strcpy(alloca(strlen(str) + 1), str);
	    str[strlen(str) - 1] = '\0';
	    options[numOptions].argInfo = POPT_ARG_STRING;
	} else {
	    options[numOptions].argInfo = POPT_ARG_NONE;
	}

	options[numOptions].val = numOptions + 1;
	options[numOptions].longName = str;

	numOptions++;
    }

    memset(options + numOptions, 0, sizeof(*options));

    argv = alloca(sizeof(*argv) * (PyList_Size(argList) + 1));
    for (i = 0; i < PyList_Size(argList); i++) {
        strObject = PyList_GetItem(argList, i);
	str = PyString_AsString(strObject);
	if (!str) return NULL;

	argv[i] = str;
    }

    argv[i] = NULL;

    optCon = poptGetContext("", PyList_Size(argList), argv,
			    options, POPT_CONTEXT_KEEP_FIRST);
    retList = PyList_New(0);
    retArgs = PyList_New(0);

    while ((rc = poptGetNextOpt(optCon)) >= 0) {
	const char * argument;

	rc--;

	if (options[rc].argInfo == POPT_ARG_STRING)
	    argument = poptGetOptArg(optCon);
	else
	    argument = NULL;
	    
	if (options[rc].longName) {
	    str = alloca(strlen(options[rc].longName) + 3);
	    sprintf(str, "--%s", options[rc].longName);
	} else {
	    str = strBuf;
	    sprintf(str, "-%c", options[rc].shortName);
	}

	if (argument) {
	    argument = strcpy(alloca(strlen(argument) + 1), argument);
	    PyList_Append(retList, 
			    Py_BuildValue("(ss)", str, argument));
	} else {
	    PyList_Append(retList, Py_BuildValue("(ss)", str, ""));
	}
    }

    if (rc < -1) {
	i = strlen(poptBadOption(optCon, POPT_BADOPTION_NOALIAS)) +
	    strlen(poptStrerror(rc));

	error = alloca(i) + 50;

	sprintf(error, "bad argument %s: %s\n", 
		poptBadOption(optCon, POPT_BADOPTION_NOALIAS), 
		poptStrerror(rc));

	PyErr_SetString(PyExc_TypeError, error);
	return NULL;
    }

    argv = (const char **) poptGetArgs(optCon);
    for (i = 0; argv && argv[i]; i++) {
	PyList_Append(retArgs, PyString_FromString(argv[i]));
    }

    poptFreeContext(optCon);

    return Py_BuildValue("(OO)", retList, retArgs);
}

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
    int readOnly = 0;
    int bindMount = 0;
    int reMount = 0;
    int flags = 0;

    if (!PyArg_ParseTuple(args, "sssiii", &fs, &device, &mntpoint,
			  &readOnly, &bindMount, &reMount)) return NULL;

    if (readOnly) flags |= IMOUNT_RDONLY; 
    if (bindMount) flags |= IMOUNT_BIND;
    if (reMount) flags |= IMOUNT_REMOUNT;

    rc = doPwMount(device, mntpoint, fs, flags, NULL);
    if (rc == IMOUNT_ERR_ERRNO) 
	PyErr_SetFromErrno(PyExc_SystemError);
    else if (rc)
	PyErr_SetString(PyExc_SystemError, "mount failed");

    if (rc) return NULL;

    Py_INCREF(Py_None);
    return Py_None;
}

#define BOOT_SIGNATURE	0xaa55	/* boot signature */
#define BOOT_SIG_OFFSET	510	/* boot signature offset */

static PyObject * doCheckBoot (PyObject * s, PyObject * args) {
    char * path;
    int fd, size;
    unsigned short magic;

    /* code from LILO */
    
    if (!PyArg_ParseTuple(args, "s", &path)) return NULL;

    if ((fd = open (path, O_RDONLY)) == -1) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    if (lseek(fd,(long) BOOT_SIG_OFFSET, 0) < 0) {
	close (fd);
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }
    
    if ((size = read(fd,(char *) &magic, 2)) != 2) {
	close (fd);
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    close (fd);
    
    return Py_BuildValue("i", magic == BOOT_SIGNATURE);
}

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

static PyObject * smpAvailable(PyObject * s, PyObject * args) {
    if (!PyArg_ParseTuple(args, "")) return NULL;

    return Py_BuildValue("i", detectSMP());
}

static PyObject * htAvailable(PyObject * s, PyObject * args) {
    if (!PyArg_ParseTuple(args, "")) return NULL;

    return Py_BuildValue("i", detectHT());
}

void init_isys(void) {
    PyObject * m, * d;

    m = Py_InitModule("_isys", isysModuleMethods);
    d = PyModule_GetDict(m);

    PyDict_SetItemString(d, "MIN_RAM", PyInt_FromLong(MIN_RAM));
    PyDict_SetItemString(d, "MIN_GUI_RAM", PyInt_FromLong(MIN_GUI_RAM));
    PyDict_SetItemString(d, "EARLY_SWAP_RAM", PyInt_FromLong(EARLY_SWAP_RAM));
}

/* FIXME: add IPv6 support once the UI changes are made   --dcantrell */
static PyObject * doConfigNetDevice(PyObject * s, PyObject * args) {
    char * dev, * ip, * netmask;
    char * gateway;
    struct pumpNetIntf cfg;
    struct in_addr addr, nm, nw;
    struct in6_addr addr6;

    if (!PyArg_ParseTuple(args, "ssss", &dev, &ip, &netmask, &gateway))
        return NULL;

    memset(&cfg,'\0',sizeof(struct pumpNetIntf));
    strncpy(cfg.device, dev, sizeof(cfg.device) - 1);

    if (inet_pton(AF_INET, ip, &addr) >= 1) {
        /* IPv4 */
        cfg.ip = ip_addr_in(&addr);
        cfg.set |= PUMP_INTFINFO_HAS_IP;

        if (inet_pton(AF_INET, netmask, &nm) >= 1) {
            cfg.netmask = ip_addr_in(&nm);
            cfg.set |= PUMP_INTFINFO_HAS_NETMASK;
        }

        cfg.network = ip_addr_v4(ntohl((addr.s_addr) & nm.s_addr));
        nw = ip_in_addr(&cfg.network);
        cfg.set |= PUMP_INTFINFO_HAS_NETWORK;

        cfg.broadcast = ip_addr_v4(ntohl(nw.s_addr | ~nm.s_addr));
        cfg.set |= PUMP_INTFINFO_HAS_BROADCAST;
    } else if (inet_pton(AF_INET6, ip, &addr) >= 1) {
        /* IPv6 */

        /* FIXME */
        return NULL;
    }

    if (strlen(gateway)) {
        if (inet_pton(AF_INET, gateway, &addr) >= 1) {
            cfg.gateway = ip_addr_in(&addr);
            cfg.set |= PUMP_NETINFO_HAS_GATEWAY;
        } else if (inet_pton(AF_INET6, gateway, &addr6) >= 1) {
            /* FIXME */
            return NULL;
        }
    }

    if (pumpSetupInterface(&cfg)) {
        PyErr_SetFromErrno(PyExc_SystemError);
        return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doDhcpNetDevice(PyObject * s, PyObject * args) {
    char * device = NULL;
    char * class = NULL;
    char * r = NULL;
    char buf[48];
    time_t timeout = 45;
    struct pumpNetIntf *pumpdev = NULL;
    /* FIXME: we call this from rescue mode, need to pass in what user wants */
    DHCP_Preference pref = DHCPv6_DISABLE_RESOLVER|DHCPv4_DISABLE_HOSTNAME_SET;
    int status, shmpump = -1, i;
    pid_t pid;
    key_t key;
    ip_addr_t *tip;
    PyObject * rc;

    /* XXX: known bug with libdhcp+libdhcp6client, disabling for now as a
     * workaround (problem started in BZ #435978)
     */
    pref |= DHCPv6_DISABLE;

    if (!PyArg_ParseTuple(args, "s|z", &device, &class))
        return NULL;

    if (class == NULL)
        class = "anaconda";

    if ((key = ftok("/tmp", 'Y')) == -1) {
        Py_INCREF(Py_None);
        return Py_None;
    }

    shmpump = shmget(key, 4096, IPC_CREAT | IPC_EXCL | 0600);
    if (shmpump == -1) {
        Py_INCREF(Py_None);
        return Py_None;
    }

    pumpdev = (struct pumpNetIntf *) shmat(shmpump, (void *) pumpdev,
                                           SHM_RND);
    if (((void *) pumpdev) == ((void *) -1)) {
        Py_INCREF(Py_None);
        return Py_None;
    }

    memset(pumpdev->device, '\0', IF_NAMESIZE);
    strncpy(pumpdev->device, device, IF_NAMESIZE);

    /* call libdhcp in a separate process because libdhcp is bad */
    pid = fork();
    if (pid == 0) {
        r = pumpDhcpClassRun(pumpdev, NULL, class, pref, 0, timeout, NULL, 0);
        if (r != NULL) {
            exit(1);
        }

        if (pumpdev->dhcp_nic) {
            i = dhcp_nic_configure(pumpdev->dhcp_nic);

            dhcp_nic_free(pumpdev->dhcp_nic);
            pumpdev->dhcp_nic = NULL;

            if (i < 0) {
                exit(2);
            }
        }

        r = pumpSetupInterface(pumpdev);
        if (r != NULL) {
            exit(3);
        }

        exit(0);
    } else if (pid == -1) {
        Py_INCREF(Py_None);
        return Py_None;
    } else {
        if (waitpid(pid, &status, 0) == -1) {
            Py_INCREF(Py_None);
            return Py_None;
        }

        if (pumpdev->numDns) {
            tip = &(pumpdev->dnsServers[0]);
            inet_ntop(tip->sa_family, IP_ADDR(tip), buf, IP_STRLEN(tip));
            rc = PyString_FromString(buf);
        } else {
            rc = PyString_FromString("");
        }

        if (shmdt(pumpdev) == -1) {
            Py_INCREF(Py_None);
            return Py_None;
        }

        if (shmctl(shmpump, IPC_RMID, 0) == -1) {
            Py_INCREF(Py_None);
            return Py_None;
        }
    }

    return rc;
}

static PyObject * doPrefixToNetmask (PyObject * s, PyObject * args) {
	int prefix = 0;
    int mask = 0;
    char dst[INET_ADDRSTRLEN];

    if (!PyArg_ParseTuple(args, "i", &prefix)) return NULL;

    mask = htonl(~((1 << (32 - prefix)) - 1));
    inet_ntop(AF_INET, (struct in_addr *) &mask, dst, INET_ADDRSTRLEN);

    return Py_BuildValue("s", dst);
}

#include <linux/fb.h>

static PyObject * doFbconProbe (PyObject * s, PyObject * args) {
    char * path;
    int fd, size;
    struct fb_fix_screeninfo fix;
    struct fb_var_screeninfo var;
    char vidres[1024], vidmode[40];
    int depth = 0;

    if (!PyArg_ParseTuple(args, "s", &path)) return NULL;
    
    if ((fd = open (path, O_RDONLY)) == -1) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    if (ioctl(fd, FBIOGET_FSCREENINFO, &fix) < 0) {
	close (fd);
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    vidres[0] = 0;    
    if (ioctl(fd, FBIOGET_VSCREENINFO, &var) >= 0 && var.pixclock) {
	int x[4], y[4], vtotal, laced = 0, dblscan = 0;
	char *p;
	double drate, hrate, vrate;
#ifdef __sparc__
	switch (fix.accel) {
	case FB_ACCEL_SUN_CREATOR:
	    var.bits_per_pixel = 24;
	    /* FALLTHROUGH */
	case FB_ACCEL_SUN_LEO:
	case FB_ACCEL_SUN_CGSIX:
	case FB_ACCEL_SUN_CG14:
	case FB_ACCEL_SUN_BWTWO:
	case FB_ACCEL_SUN_CGTHREE:
	case FB_ACCEL_SUN_TCX:
	    var.xres = var.xres_virtual;
	    var.yres = var.yres_virtual;
	    fix.smem_len = 0;
	    break;
	}
#endif
	depth = var.bits_per_pixel;
	sprintf(vidmode, "%dx%d", var.xres, var.yres);
	x[0] = var.xres;
	x[1] = x[0] + var.right_margin;
	x[2] = x[1] + var.hsync_len;
	x[3] = x[2] + var.left_margin;
	y[0] = var.yres;
	y[1] = y[0] + var.lower_margin;
	y[2] = y[1] + var.vsync_len;
	y[3] = y[2] + var.upper_margin;
	vtotal = y[3];
	drate = 1E12/var.pixclock;
	switch (var.vmode & FB_VMODE_MASK) {
	case FB_VMODE_INTERLACED: laced = 1; break;
	case FB_VMODE_DOUBLE: dblscan = 1; break;
	}
	if (dblscan) vtotal <<= 2;
	else if (!laced) vtotal <<= 1;
	hrate = drate / x[3];
	vrate = hrate / vtotal * 2;
	sprintf (vidres,
	    "Section \"Monitor\"\n"
	    "    Identifier  \"Probed Monitor\"\n"
	    "    VendorName  \"Unknown\"\n"
	    "    ModelName   \"Unknown\"\n"
	    "    HorizSync   %5.3f\n"
	    "    VertRefresh %5.3f\n"
	    "    ModeLine    \"%dx%d\" %5.3f %d %d %d %d %d %d %d %d",
	    hrate/1E3, vrate,
	    x[0], y[0],
	    drate/1E6+0.001,
	    x[0], x[1], x[2], x[3],
	    y[0], y[1], y[2], y[3]);
	if (laced) strcat (vidres, " Interlaced");
	if (dblscan) strcat (vidres, " DoubleScan");
	p = strchr (vidres, 0);
	sprintf (p, " %cHSync %cVSync",
		 (var.sync & FB_SYNC_HOR_HIGH_ACT) ? '+' : '-',
		 (var.sync & FB_SYNC_VERT_HIGH_ACT) ? '+' : '-');
	if (var.sync & FB_SYNC_COMP_HIGH_ACT)
	    strcat (vidres, " Composite");
	if (var.sync & FB_SYNC_BROADCAST)
	    strcat (vidres, " bcast");
	strcat (vidres, "\nEndSection\n");
    }

    close (fd);
    /* Allow 64K from VIDRAM to be taken for other purposes */
    size = fix.smem_len + 65536;
    /* And round down to some multiple of 256K */
    size = size & ~0x3ffff;
    /* And report in KB */
    size >>= 10;

    switch (depth) {
    case 8:
    case 16:
    case 24:
    case 32:
    	return Py_BuildValue("(iiss)", size, depth, vidmode, vidres);
    }
    return Py_BuildValue("(iiss)", size, 0, "", "");
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

    if (lseek64(fd, ((off64_t) 1024) * (off64_t) MD_NEW_SIZE_BLOCKS(size), SEEK_SET) < 0) {
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

static PyObject * doGetRaidSuperblock(PyObject * s, PyObject * args) {
    int fd;
    unsigned long size;
    mdp_super_t sb;
    char uuid[36];

    if (!PyArg_ParseTuple(args, "i", &fd)) return NULL;

    if (ioctl(fd, BLKGETSIZE, &size)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    /* put the size in 1k blocks */
    size >>= 1;

    if (lseek64(fd, ((off64_t) 1024) * (off64_t) MD_NEW_SIZE_BLOCKS(size), SEEK_SET) < 0) {
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

    sprintf(uuid, "%08x:%08x:%08x:%08x", sb.set_uuid0, sb.set_uuid1,
            sb.set_uuid2, sb.set_uuid3);

    return Py_BuildValue("(iisiiii)", sb.major_version, sb.minor_version,
		         uuid, sb.level, sb.nr_disks, sb.raid_disks,
			 sb.md_minor);
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

    if (lseek64(fd, ((off64_t) 1024) * (off64_t) MD_NEW_SIZE_BLOCKS(size), SEEK_SET) < 0) {
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

static PyObject * doRaidStop(PyObject * s, PyObject * args) {
    int fd;

    if (!PyArg_ParseTuple(args, "i", &fd)) return NULL;

    if (ioctl(fd, STOP_ARRAY, 0)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doLoadFont (PyObject * s, PyObject * args) {
    int ret;

    if (!PyArg_ParseTuple(args, "")) return NULL;

    ret = isysLoadFont ();
    if (ret) {
	errno = -ret;
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }
    
    Py_INCREF(Py_None);
    return Py_None;
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

static PyObject * doRaidStart(PyObject * s, PyObject * args) {
    int fd;
    char * dev;
    struct stat sb;

    if (!PyArg_ParseTuple(args, "is", &fd, &dev)) return NULL;

    if (stat(dev, &sb)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

#ifdef START_ARRAY
    if (ioctl(fd, START_ARRAY, (unsigned long) sb.st_rdev)) {
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }
#else
	PyErr_SetString(PyExc_SystemError, "raidautorun doesn't exist anymore!");
	return NULL;
#endif

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doResetResolv(PyObject * s, PyObject * args) {
    if (!PyArg_ParseTuple(args, "")) return NULL;

    res_init();		/* reinit the resolver so DNS changes take affect */

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doSetResolvRetry(PyObject * s, PyObject * args) {
    int count;

    if (!PyArg_ParseTuple(args, "i", &count)) return NULL;

    _res.retry = count;

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doClobberExt2 (PyObject * s, PyObject * args) {
    char * device;
    ext2_filsys fsys;
    struct ext2_super_block sb;
    int rc;

    if (!PyArg_ParseTuple(args, "s", &device)) return NULL;

    rc = ext2fs_open(device, EXT2_FLAG_FORCE, 0, 0, unix_io_manager, &fsys);

    if (rc) {
	Py_INCREF(Py_None);
	return Py_None;
    }

    memset(&sb, 0, sizeof(struct ext2_super_block));
    rc = ext2fs_initialize (device, 0, &sb, unix_io_manager, &fsys);
    if (rc) {
	Py_INCREF(Py_None);
	return Py_None;
    }

    ext2fs_close(fsys);

    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doReadE2fsLabel(PyObject * s, PyObject * args) {
    char * device;
    ext2_filsys fsys;
    char buf[50];
    int rc;

    if (!PyArg_ParseTuple(args, "s", &device)) return NULL;

    rc = ext2fs_open(device, EXT2_FLAG_FORCE, 0, 0, unix_io_manager,
		     &fsys);
    if (rc) {
	Py_INCREF(Py_None);
	return Py_None;
    }

    memset(buf, 0, sizeof(buf));
    strncpy(buf, fsys->super->s_volume_name, 
	    sizeof(fsys->super->s_volume_name));

    ext2fs_close(fsys);

    return Py_BuildValue("s", buf); 
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

static PyObject * doisPsudoTTY(PyObject * s, PyObject * args) {
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

static PyObject * getFramebufferInfo(PyObject * s, PyObject * args) {
    int fd;
    struct fb_var_screeninfo fb;

    fd = open("/dev/fb0", O_RDONLY);
    if (fd == -1) {
	Py_INCREF(Py_None);
	return Py_None;
    }

    if (ioctl(fd, FBIOGET_VSCREENINFO, &fb)) {
	close(fd);
	PyErr_SetFromErrno(PyExc_SystemError);
	return NULL;
    }

    close(fd);

    return Py_BuildValue("(iii)", fb.xres, fb.yres, fb.bits_per_pixel);
}

static PyObject * getLinkStatus(PyObject * s, PyObject * args) {
    char *dev;
    int ret;

    if (!PyArg_ParseTuple(args, "s", &dev))
	return NULL;

    ret = get_link_status(dev);
    /* returns 1 for link, 0 for no link, -1 for unknown */
    return Py_BuildValue("i", ret);
}

static PyObject * doGetMacAddress(PyObject * s, PyObject * args) {
    char *dev;
    char *ret;

    if (!PyArg_ParseTuple(args, "s", &dev))
        return NULL;

    ret = nl_mac2str(dev);

    return Py_BuildValue("s", ret);
}

static PyObject * isWireless(PyObject * s, PyObject * args) {
    char *dev;
    int ret;

    if (!PyArg_ParseTuple(args, "s", &dev))
        return NULL;

    ret = is_wireless_interface(dev);

    return Py_BuildValue("i", ret);
}

static PyObject * doGetIPAddress(PyObject * s, PyObject * args) {
    char *dev = NULL;
    char *ret = NULL;

    if (!PyArg_ParseTuple(args, "s", &dev))
        return NULL;

    ret = nl_ip2str(dev);

    return Py_BuildValue("s", ret);
}
#ifdef USESELINUX
static PyObject * doResetFileContext(PyObject * s, PyObject * args) {
    char *fn, *buf = NULL;
    char * root = NULL;
    char path[PATH_MAX];
    int ret;

    if (!PyArg_ParseTuple(args, "s|s", &fn, &root))
        return NULL;

    ret = matchpathcon(fn, 0, &buf);
    /*    fprintf(stderr, "matchpathcon returned %d: set %s to %s\n", ret, fn, buf);*/
    if (ret == 0) {
        if (root != NULL) 
            snprintf(path, PATH_MAX, "%s/%s", root, fn);
        else
            snprintf(path, PATH_MAX, "%s", root);

        ret = lsetfilecon(path, buf);
    }

    return Py_BuildValue("s", buf);
}
#endif
static PyObject * py_getDasdPorts(PyObject * o, PyObject * args) {
    if (!PyArg_ParseTuple(args, "")) return NULL;

    return Py_BuildValue("s", getDasdPorts());
}

static PyObject * py_isUsableDasd(PyObject * o, PyObject * args) {
    char *devname;
    if (!PyArg_ParseTuple(args, "s", &devname))
	return NULL;
    return Py_BuildValue("i", isUsableDasd(devname));
}

static PyObject * py_isLdlDasd(PyObject * o, PyObject * args) {
    char *devname;
    if (!PyArg_ParseTuple(args, "s", &devname))
	return NULL;
    return Py_BuildValue("i", isLdlDasd(devname));
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

static PyObject * doProbeBiosDisks(PyObject * s, PyObject * args) {
    if (!PyArg_ParseTuple(args, "")) return NULL;


    return Py_BuildValue("i", probeBiosDisks());
}

static PyObject * doGetBiosDisk(PyObject * s, PyObject * args) {
    char *mbr_sig;
    char *diskname;
            
    if (!PyArg_ParseTuple(args, "s", &mbr_sig)) return NULL;

    if ((diskname = getBiosDisk(mbr_sig)))
        return Py_BuildValue("s", diskname);

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

static PyObject * doAuditDaemon(PyObject *s) {
    audit_daemonize();
    Py_INCREF(Py_None);
    return Py_None;
}

static PyObject * doDeviceReadOnly(PyObject *s, PyObject *args) {
    char *diskname = NULL;
    int fd, is_ro;

    if (!PyArg_ParseTuple(args, "s", &diskname)) return NULL;

    fd = open(diskname, O_RDONLY);
    if (fd == -1) {
      Py_INCREF(Py_None);
      return Py_None;
    }

    if (ioctl(fd, BLKROGET, &is_ro)) {
        close(fd);
        PyErr_SetFromErrno(PyExc_SystemError);
        return NULL;
    }

    close(fd);
    if (is_ro)
        Py_RETURN_TRUE;
    else
        Py_RETURN_FALSE;
}

/* vim:set shiftwidth=4 softtabstop=4: */
