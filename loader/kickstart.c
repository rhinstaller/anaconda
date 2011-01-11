/*
 * kickstart.c - kickstart file handling
 *
 * Copyright (C) 1999, 2000, 2001, 2002, 2003  Red Hat, Inc.
 * All rights reserved.
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
 *
 * Author(s): Erik Troan <ewt@redhat.com>
 *            Matt Wilson <msw@redhat.com>
 *            Michael Fulbright <msf@redhat.com>
 *            Jeremy Katz <katzj@redhat.com>
 */

#include <Python.h>

#include <alloca.h>
#include <arpa/inet.h>
#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <newt.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include <glib.h>

#include "loader.h"
#include "loadermisc.h"
#include "lang.h"
#include "kickstart.h"
#include "modules.h"

#include "kbd.h"
#include "driverdisk.h"
#include "net.h"
#include "method.h"

#include "nfsinstall.h"
#include "urlinstall.h"
#include "cdinstall.h"
#include "hdinstall.h"

#include "../pyanaconda/isys/eddsupport.h"
#include "../pyanaconda/isys/imount.h"
#include "../pyanaconda/isys/isys.h"
#include "../pyanaconda/isys/log.h"

/* boot flags */
extern uint64_t flags;

struct ksCommandNames {
    char * name;
    void (*setupData) (struct loaderData_s *loaderData,
                       int argc, char ** argv);
} ;

static void setTextMode(struct loaderData_s * loaderData, int argc, 
                        char ** argv);
static void setGraphicalMode(struct loaderData_s * loaderData, int argc, 
                             char ** argv);
static void setCmdlineMode(struct loaderData_s * loaderData, int argc, 
                           char ** argv);
static void setSELinux(struct loaderData_s * loaderData, int argc, 
                       char ** argv);
static void setPowerOff(struct loaderData_s * loaderData, int argc, 
                        char ** argv);
static void setHalt(struct loaderData_s * loaderData, int argc, 
                    char ** argv);
static void setShutdown(struct loaderData_s * loaderData, int argc, 
                        char ** argv);
static void setMediaCheck(struct loaderData_s * loaderData, int argc, 
                          char ** argv);
static void setUpdates(struct loaderData_s * loaderData, int argc,
                       char ** argv);
static void setVnc(struct loaderData_s * loaderData, int argc,
                       char ** argv);
static void useKickstartDD(struct loaderData_s * loaderData,
                    int argc, char ** argv);
static void setKickstartKeyboard(struct loaderData_s * loaderData, int argc, 
                          char ** argv);
static void setKickstartLanguage(struct loaderData_s * loaderData, int argc, 
                          char ** argv);
static void setKickstartNetwork(struct loaderData_s * loaderData, int argc, 
                         char ** argv);
static void setKickstartCD(struct loaderData_s * loaderData, int argc, char ** argv);
static void setKickstartHD(struct loaderData_s * loaderData, int argc,
                     char ** argv);
static void setKickstartNfs(struct loaderData_s * loaderData, int argc,
                     char ** argv);
static void setKickstartUrl(struct loaderData_s * loaderData, int argc,
                     char ** argv);

struct ksCommandNames ksTable[] = {
    { "cdrom", setKickstartCD },
    { "cmdline", setCmdlineMode },
    { "device", loadKickstartModule },
    { "driverdisk", useKickstartDD },
    { "graphical", setGraphicalMode },
    { "halt", setHalt },
    { "harddrive", setKickstartHD },
    { "keyboard", setKickstartKeyboard },
    { "lang", setKickstartLanguage },
    { "mediacheck", setMediaCheck },
    { "network", setKickstartNetwork },
    { "nfs", setKickstartNfs },
    { "poweroff", setPowerOff },
    { "selinux", setSELinux },
    { "shutdown", setShutdown },
    { "text", setTextMode },
    { "updates", setUpdates },
    { "url", setKickstartUrl },
    { "vnc", setVnc },
    { NULL, NULL }
};

/* INTERNAL PYTHON INTERFACE FUNCTIONS */

static PyObject *getCallable(PyObject *module, const char *name) {
    PyObject *obj = NULL;

    obj = PyObject_GetAttrString(module, name);
    if (!obj || !PyCallable_Check(obj)) {
        Py_XDECREF(obj);
        return NULL;
    }

    return obj;
}

static PyObject *import(const char *moduleName) {
    PyObject *module = NULL;

    module = PyImport_ImportModule(moduleName);
    return module;
}

static PyObject *makeHandler(PyObject *module) {
    PyObject *func, *handler;

    func = getCallable(module, "makeVersion");
    if (!func)
        return NULL;

    handler = PyObject_CallObject(func, NULL);
    if (!handler) {
        Py_DECREF(func);
        return NULL;
    }

    Py_DECREF(func);
    return handler;
}

static PyObject *makeParser(PyObject *parserClass, PyObject *handler) {
    PyObject *parser = NULL, *args, *kwargs;

    args = PyTuple_New(1);
    PyTuple_SetItem(args, 0, handler);

    kwargs = PyDict_New();
    Py_INCREF(Py_True);
    PyDict_SetItemString(kwargs, "followIncludes", Py_True);
    Py_INCREF(Py_True);
    PyDict_SetItemString(kwargs, "errorsAreFatal", Py_True);
    Py_INCREF(Py_True);
    PyDict_SetItemString(kwargs, "missingIncludeIsFatal", Py_True);

    parser = PyObject_Call(parserClass, args, kwargs);

    Py_DECREF(kwargs);
    Py_DECREF(args);

    return parser;
}

static void handleException() {
    PyObject *ptype, *pvalue, *ptraceback;

    if (!PyErr_Occurred())
        return;

    PyErr_Fetch(&ptype, &pvalue, &ptraceback);

    startNewt();
    newtWinMessage(_("Kickstart Error"), _("OK"),
                   PyString_AsString(PyObject_Str(pvalue)));

    Py_XDECREF(ptype);
    Py_XDECREF(pvalue);
    Py_XDECREF(ptraceback);
}

/* Returns the handler.<command>.<attr> object if it exists, or NULL on error. */
static PyObject *getattr(PyObject *handler, const char *command, const char *attr) {
    PyObject *commandObj, *attrObj;

    commandObj = PyObject_GetAttrString(handler, command);
    if (!commandObj)
        return NULL;

    attrObj = PyObject_GetAttrString(commandObj, attr);
    if (!attrObj) {
        Py_DECREF(commandObj);
        return NULL;
    }

    return attrObj;
}

/* Perform the same tasks as pykickstart.parser.preprocessKickstart.  Currently
 * this is just fetching and expanding %ksappend lines.
 */
static PyObject *preprocessKickstart(PyObject *module, const char *inputFile) {
    PyObject *output = NULL, *func;

    func = getCallable(module, "preprocessKickstart");
    if (!func)
        return NULL;

    output = PyObject_CallFunctionObjArgs(func, PyString_FromString(inputFile), NULL);
    if (!output) {
        handleException();
        return NULL;
    }

    return output;
}

/* Process a kickstart file given by the filename f, as a PyObject.  This sets
 * attributes on the parser object as a side effect, returning that object or
 * NULL on exception.
 */
static PyObject *readKickstart(PyObject *parser, PyObject *f) {
    PyObject *retval;

    retval = PyObject_CallMethodObjArgs(parser, PyString_FromString("readKickstart"), f, NULL);
    if (!retval) {
        handleException();
        return NULL;
    }

    return retval;
}

int kickstartFromRemovable(char *kssrc) {
    struct device ** devices;
    char *p, *kspath;
    int i, rc;

    logMessage(INFO, "doing kickstart from removable media");
    devices = getDevices(DEVICE_DISK);
    /* usb can take some time to settle, even with the various hacks we
     * have in place. some systems use portable USB CD-ROM drives, try to
     * make sure there really isn't one before bailing. */
    for (i = 0; !devices && i < 10; ++i) {
        logMessage(INFO, "sleeping to wait for a USB disk");
        sleep(2);
        devices = getDevices(DEVICE_DISK);
    }
    if (!devices) {
        logMessage(ERROR, "no disks");
        return 1;
    }

    for (i = 0; devices[i]; i++) {
        if (devices[i]->priv.removable == 1) {
            logMessage(INFO, "first removable media is %s", devices[i]->device);
            break;
        }
    }

    if (!devices[i] || (devices[i]->priv.removable == 0)) {
        logMessage(ERROR, "no removable devices");
        return 1;
    }

    /* format is floppy:[/path/to/ks.cfg] */
    kspath = "";
    p = strchr(kssrc, ':');
    if (p)
	kspath = p + 1;

    if (!p || strlen(kspath) < 1)
	kspath = "/ks.cfg";

    if ((rc=getKickstartFromBlockDevice(devices[i]->device, kspath))) {
	if (rc == 3) {
	    startNewt();
	    newtWinMessage(_("Error"), _("OK"),
			   _("Cannot find ks.cfg on removable media."));
	}
	return 1;
    }

    return 0;
}


/* given a device name (w/o '/dev' on it), try to get ks file */
/* Error codes: 
      1 - could not create device node
      2 - could not mount device as ext2, vfat, or iso9660
      3 - kickstart file named path not there
*/
int getKickstartFromBlockDevice(char *device, char *path) {
    return getFileFromBlockDevice(device, path, "/tmp/ks.cfg");
}

void loadKickstartModule(struct loaderData_s * loaderData,
                         int argc, char **argv) {
    gchar *opts = NULL;
    gchar *module = NULL;
    gchar **args = NULL, **remaining = NULL;
    gboolean rc;
    GOptionContext *optCon = g_option_context_new(NULL);
    GError *optErr = NULL;
    GOptionEntry ksDeviceOptions[] = {
        { "opts", 0, 0, G_OPTION_ARG_STRING, &opts, NULL, NULL },
        { G_OPTION_REMAINING, 0, 0, G_OPTION_ARG_STRING_ARRAY, &remaining,
          NULL, NULL },
        { NULL },
    };

    g_option_context_set_help_enabled(optCon, FALSE);
    g_option_context_add_main_entries(optCon, ksDeviceOptions, NULL);

    if (!g_option_context_parse(optCon, &argc, &argv, &optErr)) {
        startNewt();
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Bad argument to device kickstart method "
                         "command: %s"), optErr->message);
        g_error_free(optErr);
        g_option_context_free(optCon);
        return;
    }

    g_option_context_free(optCon);

    if ((remaining != NULL) && (g_strv_length(remaining) == 1)) {
        module = remaining[0];
    }

    if (!module) {
        startNewt();
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("A module name must be specified for "
                         "the kickstart device command."));
        return;
    }

    if (opts) {
        args = g_strsplit(opts, " ", 0);
    }

    rc = mlLoadModule(module, args);
    g_strfreev(args);
    return;
}

static char *newKickstartLocation(const char *origLocation) {
    const char *location;
    char *retval = NULL;
    newtComponent f, okay, cancel, answer, locationEntry;
    newtGrid grid, buttons;

    startNewt();

    locationEntry = newtEntry(-1, -1, NULL, 60, &location, NEWT_FLAG_SCROLL);
    newtEntrySet(locationEntry, origLocation, 1);

    /* button bar at the bottom of the window */
    buttons = newtButtonBar(_("OK"), &okay, _("Cancel"), &cancel, NULL);

    grid = newtCreateGrid(1, 3);

    newtGridSetField(grid, 0, 0, NEWT_GRID_COMPONENT,
                     newtTextboxReflowed(-1, -1, _("Unable to download the kickstart file.  Please modify the kickstart parameter below or press Cancel to proceed as an interactive installation."), 60, 0, 0, 0),
                     0, 0, 0, 0, NEWT_ANCHOR_LEFT, 0);
    newtGridSetField(grid, 0, 1, NEWT_GRID_COMPONENT, locationEntry,
                     0, 1, 0, 0, NEWT_ANCHOR_LEFT, 0);
    newtGridSetField(grid, 0, 2, NEWT_GRID_SUBGRID, buttons,
                     0, 1, 0, 0, 0, NEWT_GRID_FLAG_GROWX);

    f = newtForm(NULL, NULL, 0);
    newtGridAddComponentsToForm(grid, f, 1);
    newtGridWrappedWindow(grid, _("Error downloading kickstart file"));
    newtGridFree(grid, 1);

    /* run the form */
    answer = newtRunForm(f);

    if (answer != cancel)
        retval = strdup(location);

    newtFormDestroy(f);
    newtPopWindow();

    return retval;
}

int isKickstartFileRemote(char *ksFile) {
    char *location = NULL;

    if (ksFile == NULL) {
        return 0;
    }

    if (!strcmp(ksFile, "ks")) {
       return 1;
    } else if (!strncmp(ksFile, "ks=", 3)) {
        location = ksFile + 3;
    }

    if (!strncmp(location, "http", 4) ||
        !strncmp(location, "ftp://", 6) ||
        !strncmp(location, "nfs:", 4)) {
        return 1;
    } else {
        return 0;
    }
}

void getKickstartFile(struct loaderData_s *loaderData) {
    char *c;
    int rc = 1;

    /* Chop off the parameter name, if given. */
    if (!strncmp(loaderData->ksFile, "ks=", 3))
        c = loaderData->ksFile+3;
    else
        c = loaderData->ksFile;

    while (rc != 0) {
        if (!strncmp(c, "ks", 2)) {
            rc = kickstartFromNfs(NULL, loaderData);
            loaderData->ksFile = strdup("/tmp/ks.cfg");
        } else if (!strncmp(c, "http", 4) || !strncmp(c, "ftp://", 6)) {
            rc = kickstartFromUrl(c, loaderData);
            loaderData->ksFile = strdup("/tmp/ks.cfg");
        } else if (!strncmp(c, "nfs:", 4)) {
            rc = kickstartFromNfs(c+4, loaderData);
            loaderData->ksFile = strdup("/tmp/ks.cfg");
        } else if (!strncmp(c, "floppy", 6)) {
            rc = kickstartFromRemovable(c);
            loaderData->ksFile = strdup("/tmp/ks.cfg");
        } else if (!strncmp(c, "hd:", 3)) {
            rc = kickstartFromHD(c);
            loaderData->ksFile = strdup("/tmp/ks.cfg");
        } else if (!strncmp(c, "bd:", 3)) {
            rc = kickstartFromBD(c);
            loaderData->ksFile = strdup("/tmp/ks.cfg");
        } else if (!strncmp(c, "cdrom", 5)) {
            rc = kickstartFromCD(c);
            loaderData->ksFile = strdup("/tmp/ks.cfg");
        } else if (!strncmp(c, "file:", 5)) {
            loaderData->ksFile = c+5;
            break;
        }

        if (rc != 0) {
            char *newLocation;

            if (!strcmp(c, "ks"))
                newLocation = newKickstartLocation("");
            else
                newLocation = newKickstartLocation(c);

            if (loaderData->ksFile != NULL)
                free(loaderData->ksFile);

            if (newLocation != NULL) {
               loaderData->ksFile = strdup(newLocation);
               free(newLocation);
               return getKickstartFile(loaderData);
            }
            else
               return;
        }
    }

    flags |= LOADER_FLAGS_KICKSTART;
    return;
}

static void setVnc(struct loaderData_s * loaderData, int argc,
                   char ** argv) {
    logMessage(INFO, "kickstart forcing graphical mode over vnc");
    flags |= LOADER_FLAGS_GRAPHICAL | LOADER_FLAGS_EARLY_NETWORKING;
    return;
}

static void setUpdates(struct loaderData_s * loaderData, int argc,
                       char ** argv) {
   if (argc == 1)
      flags |= LOADER_FLAGS_UPDATES;
   else if (argc == 2)
      loaderData->updatessrc = strdup(argv[1]);
   else
      logMessage(WARNING, "updates command given with incorrect arguments");
}

static void setTextMode(struct loaderData_s * loaderData, int argc, 
                        char ** argv) {
    logMessage(INFO, "kickstart forcing text mode");
    flags |= LOADER_FLAGS_TEXT;
    return;
}

static void setGraphicalMode(struct loaderData_s * loaderData, int argc, 
                        char ** argv) {
    logMessage(INFO, "kickstart forcing graphical mode");
    flags |= LOADER_FLAGS_GRAPHICAL;
    return;
}

static void setCmdlineMode(struct loaderData_s * loaderData, int argc, 
                           char ** argv) {
    logMessage(INFO, "kickstart forcing cmdline mode");
    flags |= LOADER_FLAGS_CMDLINE;
    return;
}

static void setSELinux(struct loaderData_s * loaderData, int argc, 
                       char ** argv) {
    flags |= LOADER_FLAGS_SELINUX;
    return;
}

static void setPowerOff(struct loaderData_s * loaderData, int argc, 
                        char ** argv) {
    if (!FL_NOKILL(flags))
        flags |= LOADER_FLAGS_POWEROFF;
    return;
}

static void setHalt(struct loaderData_s * loaderData, int argc, 
                    char ** argv) {
    if (!FL_NOKILL(flags))
        flags |= LOADER_FLAGS_HALT;
    return;
}

static void setShutdown(struct loaderData_s * loaderData, int argc, 
                    char ** argv) {
    gint eject = 0, reboot = 0, halt = 0, poweroff = 0;
    GOptionContext *optCon = g_option_context_new(NULL);
    GError *optErr = NULL;
    GOptionEntry ksOptions[] = {
        { "eject", 'e', 0, G_OPTION_ARG_INT, &eject, NULL, NULL },
        { "reboot", 'r', 0, G_OPTION_ARG_INT, &reboot, NULL, NULL },
        { "halt", 'h', 0, G_OPTION_ARG_INT, &halt, NULL, NULL },
        { "poweroff", 'p', 0, G_OPTION_ARG_INT, &poweroff, NULL, NULL },
        { NULL },
    };

    g_option_context_set_help_enabled(optCon, FALSE);
    g_option_context_add_main_entries(optCon, ksOptions, NULL);

    if (!g_option_context_parse(optCon, &argc, &argv, &optErr)) {
        startNewt();
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Bad argument to shutdown kickstart method "
                         "command: %s"), optErr->message);
        g_error_free(optErr);
        g_option_context_free(optCon);
        return;
    }

    g_option_context_free(optCon);

    if (FL_NOKILL(flags)) {
        flags |= LOADER_FLAGS_HALT;
    } else  {
        if (poweroff)
            flags |= LOADER_FLAGS_POWEROFF;
        if ((!poweroff && !reboot) || (halt))
            flags |= LOADER_FLAGS_HALT;
    }
}

static void setMediaCheck(struct loaderData_s * loaderData, int argc, 
                          char ** argv) {
    flags |= LOADER_FLAGS_MEDIACHECK;
    return;
}

static void useKickstartDD(struct loaderData_s * loaderData,
                    int argc, char ** argv) {
    char * dev = NULL;
    char * biospart = NULL, * p = NULL; 
    gchar *fstype = NULL, *src = NULL;
    gint usebiosdev = 0;
    gchar **remaining = NULL;
    GOptionContext *optCon = g_option_context_new(NULL);
    GError *optErr = NULL;
    GOptionEntry ksDDOptions[] = {
        /* The --type option is deprecated and now has no effect. */
        { "type", 0, 0, G_OPTION_ARG_STRING, &fstype, NULL, NULL },
        { "source", 0, 0, G_OPTION_ARG_STRING, &src, NULL, NULL },
        { "biospart", 0, 0, G_OPTION_ARG_INT, &usebiosdev, NULL, NULL },
        { G_OPTION_REMAINING, 0, 0, G_OPTION_ARG_STRING_ARRAY, &remaining,
          NULL, NULL },
        { NULL },
    };

    g_option_context_set_help_enabled(optCon, FALSE);
    g_option_context_add_main_entries(optCon, ksDDOptions, NULL);

    if (!g_option_context_parse(optCon, &argc, &argv, &optErr)) {
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("The following invalid argument was specified for "
                         "the kickstart driver disk command: %s"),
                       optErr->message);
        g_error_free(optErr);
        g_option_context_free(optCon);
        g_strfreev(remaining);
        return;
    }

    g_option_context_free(optCon);

    if ((remaining != NULL) && (g_strv_length(remaining) == 1)) {
        dev = remaining[0];
    }

    if (!dev && !src) {
        logMessage(ERROR, "bad arguments to kickstart driver disk command");
        return;
    }

    if (usebiosdev != 0) {
        p = strchr(dev,'p');
        if (!p){
            logMessage(ERROR, "Bad argument for biospart");
            return;
        }
        *p = '\0';
        
        biospart = getBiosDisk(dev);
        if (biospart == NULL) {
            logMessage(ERROR, "Unable to locate BIOS dev %s",dev);
            return;
        }
        dev = malloc(strlen(biospart) + strlen(p + 1) + 2);
        sprintf(dev, "%s%s", biospart, p + 1);
    }

    if (dev) {
        getDDFromDev(loaderData, dev, NULL);
    } else {
        getDDFromSource(loaderData, src, NULL);
    }

    g_strfreev(remaining);
    return;
}

static void setKickstartKeyboard(struct loaderData_s * loaderData, int argc, 
                          char ** argv) {
    if (argc < 2) {
        logMessage(ERROR, "no argument passed to keyboard kickstart command");
        return;
    }

    loaderData->kbd = argv[1];
    loaderData->kbd_set = 1;
}

static void setKickstartLanguage(struct loaderData_s * loaderData, int argc, 
                          char ** argv) {
    if (argc < 2) {
        logMessage(ERROR, "no argument passed to lang kickstart command");
        return;
    }

    loaderData->lang = argv[1];
    loaderData->lang_set = 1;
}

static void setKickstartNetwork(struct loaderData_s * loaderData, int argc, 
                         char ** argv) {
    iface_t iface;
    gchar *bootProto = NULL, *device = NULL, *class = NULL, *ethtool = NULL;
    gchar *essid = NULL, *wepkey = NULL, *onboot = NULL, *gateway = NULL;
    gint mtu = 1500, dhcpTimeout = -1;
    gboolean noipv4 = FALSE, noipv6 = FALSE, noDns = FALSE, noksdev = FALSE;
    GOptionContext *optCon = g_option_context_new(NULL);
    GError *optErr = NULL;
    struct in_addr addr;
#ifdef ENABLE_IPV6
    struct in6_addr addr6;
#endif
    int rc;
    GOptionEntry ksOptions[] = {
        { "bootproto", 0, 0, G_OPTION_ARG_STRING, &bootProto, NULL, NULL },
        { "device", 0, 0, G_OPTION_ARG_STRING, &device, NULL, NULL },
        { "dhcpclass", 0, 0, G_OPTION_ARG_STRING, &class, NULL, NULL },
        { "gateway", 'g', 0, G_OPTION_ARG_STRING, &gateway,
          NULL, NULL },
        { "ip", 'i', 0, G_OPTION_ARG_STRING, &loaderData->ipv4, NULL, NULL },
#ifdef ENABLE_IPV6
        { "ipv6", 0, 0, G_OPTION_ARG_STRING, &loaderData->ipv6, NULL, NULL },
#endif
        { "mtu", 0, 0, G_OPTION_ARG_INT, &mtu, NULL, NULL },
        { "nameserver", 'n', 0, G_OPTION_ARG_STRING, &loaderData->dns,
          NULL, NULL },
        { "netmask", 'm', 0, G_OPTION_ARG_STRING, &loaderData->netmask,
          NULL, NULL },
        { "noipv4", 0, 0, G_OPTION_ARG_NONE, &noipv4, NULL, NULL },
        { "noipv6", 0, 0, G_OPTION_ARG_NONE, &noipv6, NULL, NULL },
        { "nodns", 0, 0, G_OPTION_ARG_NONE, &noDns, NULL, NULL },
        { "hostname", 'h', 0, G_OPTION_ARG_STRING, &loaderData->hostname,
          NULL, NULL },
        { "ethtool", 0, 0, G_OPTION_ARG_STRING, &ethtool, NULL, NULL },
        { "essid", 0, 0, G_OPTION_ARG_STRING, &essid, NULL, NULL },
        { "wepkey", 0, 0, G_OPTION_ARG_STRING, &wepkey, NULL, NULL },
        { "onboot", 0, 0, G_OPTION_ARG_STRING, &onboot, NULL, NULL },
        { "notksdevice", 0, 0, G_OPTION_ARG_NONE, &noksdev, NULL, NULL },
        { "dhcptimeout", 0, 0, G_OPTION_ARG_INT, &dhcpTimeout, NULL, NULL },
        { NULL },
    };

    iface_init_iface_t(&iface);

    g_option_context_set_help_enabled(optCon, FALSE);
    g_option_context_add_main_entries(optCon, ksOptions, NULL);

    if (!g_option_context_parse(optCon, &argc, &argv, &optErr)) {
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Bad argument to kickstart network command: %s"),
                       optErr->message);
        g_error_free(optErr);
    }

    g_option_context_free(optCon);

    /* if they've specified dhcp/bootp use dhcp for the interface */
    if (bootProto && (!strncmp(bootProto, "dhcp", 4) || 
                       !strncmp(bootProto, "bootp", 4))) {
        loaderData->ipv4 = strdup("dhcp");
        loaderData->ipinfo_set = 1;
    } else if (loaderData->ipv4) {
        /* JKFIXME: this assumes a bit... */
        loaderData->ipinfo_set = 1;
    }

    /* now make sure the specified bootproto is valid */
    if (bootProto && strcmp(bootProto, "dhcp") && strcmp(bootProto, "bootp") &&
        strcmp(bootProto, "static") && strcmp(bootProto, "query")) {
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Bad bootproto %s specified in network command"),
                       bootProto);
    }

    /* --gateway is common for ipv4 and ipv6, same as in loader UI */
    if (gateway) {
        if ((rc = inet_pton(AF_INET, gateway, &addr)) == 1) {
            loaderData->gateway = strdup(gateway);
        } else if (rc == 0) {
#ifdef ENABLE_IPV6
            if ((rc = inet_pton(AF_INET6, gateway, &addr6)) == 1) {
                loaderData->gateway6 = strdup(gateway);
            } else if (rc == 0) {
#endif
                logMessage(WARNING,
                           "invalid address in kickstart --gateway");
#ifdef ENABLE_IPV6
            } else {
                 logMessage(ERROR, "%s (%d): %s", __func__, __LINE__,
                               strerror(errno));
            }
#endif
        } else {
            logMessage(ERROR, "%s (%d): %s", __func__, __LINE__,
                       strerror(errno));
        }
    }

    if (!noksdev) {
        if (device) {
            /* If --device=MAC was given, translate into a device name now. */
            if (index(device, ':') != NULL)
                loaderData->netDev = iface_mac2device(device);
            else
                loaderData->netDev = strdup(device);

            loaderData->netDev_set = 1;
        }

        if (class) {
            loaderData->netCls = strdup(class);
            loaderData->netCls_set = 1;
        }

        if (ethtool) {
            if (loaderData->ethtool)
                free(loaderData->ethtool);
            loaderData->ethtool = strdup(ethtool);
            free(ethtool);
        }

        if (essid) {
            if (loaderData->essid)
                free(loaderData->essid);
            loaderData->essid = strdup(essid);
            free(essid);
        }

        if (wepkey) {
            if (loaderData->wepkey)
                free(loaderData->wepkey);
            loaderData->wepkey = strdup(wepkey);
            free(wepkey);
        }

        if (mtu) {
           loaderData->mtu = mtu;
        }

        if (noipv4)
            flags |= LOADER_FLAGS_NOIPV4;

#ifdef ENABLE_IPV6
        if (noipv6)
            flags |= LOADER_FLAGS_NOIPV6;

        if (loaderData->ipv6) {
            loaderData->ipv6info_set = 1;
        }
#endif
    }

    if (noDns) {
        loaderData->noDns = 1;
    }

    /* Make sure the network is always up if there's a network line in the
     * kickstart file, as %post/%pre scripts might require that.
     */
    if (loaderData->method != METHOD_NFS && loaderData->method != METHOD_URL) {
        if (kickstartNetworkUp(loaderData, &iface))
            logMessage(ERROR, "unable to bring up network");
    }
}

static void setKickstartCD(struct loaderData_s * loaderData, int argc, char ** argv) {
    logMessage(INFO, "kickstartFromCD");
    loaderData->method = METHOD_CDROM;
}

static void setKickstartHD(struct loaderData_s * loaderData, int argc,
                     char ** argv) {
    char *p;
    gchar *biospart = NULL, *partition = NULL, *dir = NULL;
    GOptionContext *optCon = g_option_context_new(NULL);
    GError *optErr = NULL;
    GOptionEntry ksHDOptions[] = {
        { "biospart", 0, 0, G_OPTION_ARG_STRING, &biospart, NULL, NULL },
        { "partition", 0, 0, G_OPTION_ARG_STRING, &partition, NULL, NULL },
        { "dir", 0, 0, G_OPTION_ARG_STRING, &dir, NULL, NULL },
        { NULL },
    };

    logMessage(INFO, "kickstartFromHD");

    g_option_context_set_help_enabled(optCon, FALSE);
    g_option_context_add_main_entries(optCon, ksHDOptions, NULL);

    if (!g_option_context_parse(optCon, &argc, &argv, &optErr)) {
        startNewt();
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Bad argument to HD kickstart method "
                         "command: %s"), optErr->message);
        g_error_free(optErr);
        g_option_context_free(optCon);
        return;
    }

    g_option_context_free(optCon);

    if (biospart) {
        char * dev;

        p = strchr(biospart,'p');
        if(!p){
            logMessage(ERROR, "Bad argument for --biospart");
            return;
        }
        *p = '\0';
        dev = getBiosDisk(biospart);
        if (dev == NULL) {
            logMessage(ERROR, "Unable to location BIOS partition %s", biospart);
            return;
        }
        partition = malloc(strlen(dev) + strlen(p + 1) + 2);
        sprintf(partition, "%s%s", dev, p + 1);
    }

    loaderData->method = METHOD_HD;
    checked_asprintf(&loaderData->instRepo, "hd:%s:%s", partition, dir);

    logMessage(INFO, "results of hd ks, partition is %s, dir is %s", partition,
               dir);
}

static void setKickstartNfs(struct loaderData_s * loaderData, int argc,
                     char ** argv) {
    gchar *host = NULL, *dir = NULL, *mountOpts = NULL;
    GOptionContext *optCon = g_option_context_new(NULL);
    GError *optErr = NULL;
    GOptionEntry ksNfsOptions[] = {
        { "server", 0, 0, G_OPTION_ARG_STRING, &host, NULL, NULL },
        { "dir", 0, 0, G_OPTION_ARG_STRING, &dir, NULL, NULL },
        { "opts", 0, 0, G_OPTION_ARG_STRING, &mountOpts, NULL, NULL },
        { NULL },
    };

    logMessage(INFO, "kickstartFromNfs");

    g_option_context_set_help_enabled(optCon, FALSE);
    g_option_context_add_main_entries(optCon, ksNfsOptions, NULL);

    if (!g_option_context_parse(optCon, &argc, &argv, &optErr)) {
        startNewt();
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Bad argument to NFS kickstart method "
                         "command: %s"), optErr->message);
        g_error_free(optErr);
        g_option_context_free(optCon);
        return;
    }

    g_option_context_free(optCon);

    if (!host || !dir) {
        logMessage(ERROR, "host and directory for nfs kickstart not specified");
        return;
    }

    logMessage(INFO, "results of nfs, host is %s, dir is %s, opts are '%s'",
               host, dir, mountOpts);

    loaderData->method = METHOD_NFS;
    if (mountOpts) {
        checked_asprintf(&loaderData->instRepo, "nfs:%s:%s:%s", host, mountOpts, dir);
    } else {
        checked_asprintf(&loaderData->instRepo, "nfs:%s:%s", host, dir);
    }
}

static void setKickstartUrl(struct loaderData_s * loaderData, int argc,
                     char ** argv) {
    gchar *url = NULL, *proxy = NULL;
    gboolean noverifyssl = FALSE;
    GOptionContext *optCon = g_option_context_new(NULL);
    GError *optErr = NULL;
    GOptionEntry ksUrlOptions[] = {
        { "url", 0, 0, G_OPTION_ARG_STRING, &url, NULL, NULL },
        { "proxy", 0, 0, G_OPTION_ARG_STRING, &proxy, NULL, NULL },
        { "noverifyssl", 0, 0, G_OPTION_ARG_NONE, &noverifyssl, NULL, NULL },
        { NULL },
    };

    logMessage(INFO, "kickstartFromUrl");

    g_option_context_set_help_enabled(optCon, FALSE);
    g_option_context_add_main_entries(optCon, ksUrlOptions, NULL);

    if (!g_option_context_parse(optCon, &argc, &argv, &optErr)) {
        startNewt();
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Bad argument to URL kickstart method "
                         "command: %s"), optErr->message);
        g_error_free(optErr);
        g_option_context_free(optCon);
        return;
    }

    g_option_context_free(optCon);

    if (!url) {
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Must supply a --url argument to Url kickstart method."));
        return;
    }

    /* determine install type */
    if (strncmp(url, "http", 4) && strncmp(url, "ftp://", 6)) {
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Unknown Url method %s"), url);
        return;
    }

    loaderData->instRepo = strdup(url);
    loaderData->instRepo_noverifyssl = noverifyssl;
    loaderData->method = METHOD_URL;

    if (proxy) {
        splitProxyParam(proxy, &loaderData->proxyUser,
			       &loaderData->proxyPassword,
			       &loaderData->proxy);
    }
    logMessage(INFO, "results of url ks, url %s", url);
}

int runKickstart(struct loaderData_s * loaderData, const char *file) {
    PyObject *versionMod, *parserMod = NULL;
    PyObject *handler, *parser;
    PyObject *processedFile;
    int rc = 0;

    PyObject *callable = NULL;

    logMessage(INFO, "setting up kickstart");

    Py_Initialize();

    if ((versionMod = import("pykickstart.version")) == NULL)
        goto quit;

    if ((parserMod = import("pykickstart.parser")) == NULL)
        goto quit;

    /* make the KickstartHandler object */
    if ((handler = makeHandler(versionMod)) == NULL)
        goto quit;

    /* make the KickstartParser object */
    if ((callable = getCallable(parserMod, "KickstartParser")) == NULL)
        goto quit;
    else
        parser = makeParser(callable, handler);

    /* call preprocessKickstart */
    processedFile = preprocessKickstart(parserMod, file);

    /* call readKickstart */
    if (processedFile) {
        struct ksCommandNames *cmd;

        if (!readKickstart(parser, processedFile))
            goto quit;

        /* Now handler is set up with all the kickstart data.  Run through
         * every element of the ksTable and run its function.  The functions
         * themselves will decide if they should do anything or not.
         */
        for (cmd = ksTable; cmd->name; cmd++)
            cmd->setupData(loaderData, 0, NULL);
    }

    rc = 1;

quit:
    Py_XDECREF(versionMod);
    Py_XDECREF(callable);
    Py_XDECREF(parserMod);
    Py_Finalize();
    return rc;
}

/* vim:set sw=4 sts=4 et: */
