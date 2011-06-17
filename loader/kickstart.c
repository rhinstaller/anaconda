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
#include "ibft.h"

#include "nfsinstall.h"
#include "urlinstall.h"
#include "cdinstall.h"
#include "hdinstall.h"

#include "../pyanaconda/isys/eddsupport.h"
#include "../pyanaconda/isys/imount.h"
#include "../pyanaconda/isys/isys.h"
#include "../pyanaconda/isys/log.h"

/* Too bad, but we need constants visible everywhere. */
static PyObject *constantsMod;

/* boot flags */
extern uint64_t flags;

static void setDisplayMode(struct loaderData_s * loaderData, PyObject *handler);
static void setSELinux(struct loaderData_s * loaderData, PyObject *handler);
static void setMediaCheck(struct loaderData_s * loaderData, PyObject *handler);
static void setUpdates(struct loaderData_s * loaderData, PyObject *handler);
static void setVnc(struct loaderData_s * loaderData, PyObject *handler);
static void useKickstartDD(struct loaderData_s * loaderData, PyObject *handler);
static void setKickstartKeyboard(struct loaderData_s * loaderData, PyObject *handler);
static void setKickstartLanguage(struct loaderData_s * loaderData, PyObject *handler);
static void setKickstartNetwork(struct loaderData_s * loaderData, PyObject *handler);
static void setKickstartCD(struct loaderData_s * loaderData, PyObject *handler);
static void setKickstartHD(struct loaderData_s * loaderData, PyObject *handler);
static void setKickstartNfs(struct loaderData_s * loaderData, PyObject *handler);
static void setKickstartUrl(struct loaderData_s * loaderData, PyObject *handler);
static void loadKickstartModule(struct loaderData_s * loaderData, PyObject *handler);

typedef void (*commandFunc_t)(struct loaderData_s *loaderData, PyObject *handler);

commandFunc_t ksTable[] = {
    &loadKickstartModule,
    &setDisplayMode,
    &setKickstartCD,
    &setKickstartHD,
    &setKickstartKeyboard,
    &setKickstartLanguage,
    &setKickstartNfs,
    &setKickstartUrl,
    &setVnc,
    &setKickstartNetwork,
    &setMediaCheck,
    &setSELinux,
    &setUpdates,
    &useKickstartDD,
    NULL
};

/* INTERNAL PYTHON INTERFACE FUNCTIONS */

static PyObject *getObject(PyObject *module, const char *name, unsigned int isCallable) {
    PyObject *obj = NULL;

    obj = PyObject_GetAttrString(module, name);
    if (!obj)
        return NULL;

    if (isCallable && !PyCallable_Check(obj)) {
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

    func = getObject(module, "makeVersion", 1);
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
    Py_INCREF(Py_False);
    PyDict_SetItemString(kwargs, "missingIncludeIsFatal", Py_False);

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
    PyObject *commandObj = NULL, *attrObj = NULL;

    commandObj = PyObject_GetAttrString(handler, command);
    if (!commandObj)
        goto cleanup;

    attrObj = PyObject_GetAttrString(commandObj, attr);
    if (!attrObj)
        goto cleanup;

cleanup:
    Py_XDECREF(commandObj);
    return attrObj;
}

static PyObject *getDataList(PyObject *handler, const char *command) {
    PyObject *attrObj = getattr(handler, command, "dataList");
    PyObject *retval = NULL;

    if (!attrObj || !PyCallable_Check(attrObj))
        goto cleanup;

    retval = PyObject_CallObject(attrObj, NULL);

cleanup:
    Py_XDECREF(attrObj);
    return retval;
}

/* Perform the same tasks as pykickstart.parser.preprocessKickstart.  Currently
 * this is just fetching and expanding %ksappend lines.
 */
static PyObject *preprocessKickstart(PyObject *module, const char *inputFile) {
    PyObject *output = NULL, *func;

    func = getObject(module, "preprocessKickstart", 1);
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

/* PYTHON HELPERS */

static unsigned int isNotEmpty(PyObject *obj) {
    return obj && PyString_Check(obj) && strcmp("", PyString_AsString(obj));
}

static unsigned int objIsStr(PyObject *obj, const char *str) {
    return obj && PyString_Check(obj) && !strcmp(str, PyString_AsString(obj));
}

static unsigned int isTrue(PyObject *obj) {
    return obj && PyBool_Check(obj) && obj == Py_True;
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

void loadKickstartModule(struct loaderData_s * loaderData, PyObject *handler) {
    Py_ssize_t i;
    PyObject *list = getDataList(handler, "device");

    if (!list)
        return;

    for (i = 0; i < PyList_Size(list); i++) {
        PyObject *ele = PyList_GetItem(list, i);
        PyObject *moduleName, *moduleOpts;

        if (!ele)
            continue;

        moduleName = getObject(ele, "moduleName", 0);
        moduleOpts = getObject(ele, "moduleOpts", 0);

        if (isNotEmpty(moduleName)) {
            if (isNotEmpty(moduleOpts)) {
                gchar **args = g_strsplit(PyString_AsString(moduleOpts), " ", 0);
                mlLoadModule(PyString_AsString(moduleName), args);
                g_strfreev(args);
            }  else
                mlLoadModule(PyString_AsString(moduleName), NULL);
        }

        Py_XDECREF(moduleName);
        Py_XDECREF(moduleOpts);
    }

    Py_XDECREF(list);
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

    return isURLRemote(location);
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

static void setVnc(struct loaderData_s * loaderData, PyObject *handler) {
    PyObject *vncEnabled = getattr(handler, "vnc", "enabled");

    if (isTrue(vncEnabled)) {
        logMessage(INFO, "kickstart forcing graphical mode over vnc");
        flags |= LOADER_FLAGS_GRAPHICAL | LOADER_FLAGS_EARLY_NETWORKING;
    }

    Py_XDECREF(vncEnabled);
}

static void setUpdates(struct loaderData_s * loaderData, PyObject *handler) {
    PyObject *url = getattr(handler, "updates", "url");

    if (isNotEmpty(url)) {
        if (objIsStr(url, "floppy"))
            flags |= LOADER_FLAGS_UPDATES;
        else
            loaderData->updatessrc = strdup(PyString_AsString(url));
    }

    Py_XDECREF(url);
}

static void setDisplayMode(struct loaderData_s * loaderData, PyObject *handler) {
    PyObject *textObj = getObject(constantsMod, "DISPLAY_MODE_TEXT", 0);
    PyObject *cmdlineObj = getObject(constantsMod, "DISPLAY_MODE_CMDLINE", 0);
    PyObject *settingObj = getattr(handler, "displaymode", "displayMode");

    if (!settingObj)
        goto cleanup;

    if (settingObj == textObj) {
        logMessage(INFO, "kickstart forcing text mode");
        flags |= LOADER_FLAGS_TEXT;
    } else if (settingObj == cmdlineObj) {
        logMessage(INFO, "kickstart forcing cmdline mode");
        flags |= LOADER_FLAGS_CMDLINE;
    } else {
        logMessage(INFO, "kickstart forcing graphical mode");
        flags |= LOADER_FLAGS_GRAPHICAL;
    }

cleanup:
    Py_XDECREF(textObj);
    Py_XDECREF(cmdlineObj);
    Py_XDECREF(settingObj);
}

static void setSELinux(struct loaderData_s * loaderData, PyObject *handler) {
    PyObject *disabledObj = getObject(constantsMod, "SELINUX_DISABLED", 0);
    PyObject *settingObj = getattr(handler, "selinux", "selinux");

    if (settingObj && settingObj != disabledObj)
        flags |= LOADER_FLAGS_SELINUX;

    Py_XDECREF(disabledObj);
    Py_XDECREF(settingObj);
}

static void setMediaCheck(struct loaderData_s * loaderData, PyObject *handler) {
    PyObject *mediaCheckEnabled = getattr(handler, "mediacheck", "mediacheck");

    if (isTrue(mediaCheckEnabled))
        flags |= LOADER_FLAGS_MEDIACHECK;

    Py_XDECREF(mediaCheckEnabled);
}

static void useKickstartDD(struct loaderData_s * loaderData, PyObject *handler) {
    Py_ssize_t i;
    PyObject *list = getDataList(handler, "driverdisk");

    if (!list)
        return;

    for (i = 0; i < PyList_Size(list); i++) {
        PyObject *ele = PyList_GetItem(list, i);
        PyObject *attr;

        if (!ele)
            continue;

        attr = getObject(ele, "source", 0);
        if (isNotEmpty(attr)) {
            getDDFromSource(loaderData, PyString_AsString(attr), NULL);
            goto cleanup;
        }

        Py_XDECREF(attr);
        attr = getObject(ele, "partition", 0);

        if (isNotEmpty(attr)) {
            getDDFromDev(loaderData, PyString_AsString(attr), NULL);
            goto cleanup;
        }

        Py_XDECREF(attr);
        attr = getObject(ele, "biospart", 0);

        if (isNotEmpty(attr)) {
            char *dev = strdup(PyString_AsString(attr));
            char *biospart = NULL, *p = NULL;

            p = strchr(dev,'p');
            if (!p){
                logMessage(ERROR, "Bad argument for biospart");
                goto cleanup;
            }
            *p = '\0';

            biospart = getBiosDisk(dev);
            if (biospart == NULL) {
                logMessage(ERROR, "Unable to locate BIOS dev %s",dev);
                goto cleanup;
            }

            free(dev);
            dev = malloc(strlen(biospart) + strlen(p + 1) + 2);
            sprintf(dev, "%s%s", biospart, p + 1);
            getDDFromDev(loaderData, dev, NULL);
        }

cleanup:
        Py_XDECREF(attr);
    }

    Py_XDECREF(list);
}

static void setKickstartKeyboard(struct loaderData_s * loaderData, PyObject *handler) {
    PyObject *kbdObj = getattr(handler, "keyboard", "keyboard");

    if (isNotEmpty(kbdObj)) {
        loaderData->kbd = strdup(PyString_AsString(kbdObj));
        loaderData->kbd_set = 1;
    }

    Py_XDECREF(kbdObj);
}

static void setKickstartLanguage(struct loaderData_s * loaderData, PyObject *handler) {
    PyObject *langObj = getattr(handler, "lang", "lang");

    if (isNotEmpty(langObj)) {
        loaderData->lang = strdup(PyString_AsString(langObj));
        loaderData->lang_set = 1;
    }

    Py_XDECREF(langObj);
}

static void _setNetworkString(PyObject *obj, const char *name, char **dest, int *sentinel) {
    PyObject *attr = getObject(obj, name, 0);

    if (!isNotEmpty(attr))
        goto cleanup;

    if (*dest)
        free(*dest);
    *dest = strdup(PyString_AsString(attr));

    Py_XDECREF(attr);

    if (sentinel)
        *sentinel = 1;

cleanup:
    Py_XDECREF(attr);
}

int process_kickstart_wifi (struct loaderData_s * loaderData) {
    int rc = -1;

    if (loaderData->essid != NULL) {
        if (loaderData->wepkey != NULL) {
            rc = add_and_activate_wifi_connection(&(loaderData->netDev), loaderData->essid,
                    WIFI_PROTECTION_WEP, loaderData->wepkey, loaderData->ipinfo_set, loaderData->ipv4,
                    loaderData->gateway, loaderData->dns, loaderData->netmask);
        }
        else if (loaderData->wpakey != NULL) {
            rc = add_and_activate_wifi_connection(&(loaderData->netDev), loaderData->essid,
                    WIFI_PROTECTION_WPA, loaderData->wpakey, loaderData->ipinfo_set, loaderData->ipv4,
                    loaderData->gateway, loaderData->dns, loaderData->netmask);
        }
        else {
            rc = add_and_activate_wifi_connection(&(loaderData->netDev), loaderData->essid,
                    WIFI_PROTECTION_UNPROTECTED, NULL, loaderData->ipinfo_set, loaderData->ipv4,
                    loaderData->gateway, loaderData->dns, loaderData->netmask);
        }
    }

    if (rc == WIFI_ACTIVATION_OK) loaderData->netDev_set = 1;
    else logMessage(ERROR, "wifi activation in kickstart failed");

    return rc;
}


static void setKickstartNetwork(struct loaderData_s * loaderData, PyObject *handler) {
    Py_ssize_t i;
    PyObject *list = getDataList(handler, "network");
    iface_t iface;
    gboolean device_flushed = FALSE;
    char *cmdline_device = NULL;

    if (!list)
        return;

    for (i = 0; i < PyList_Size(list); i++) {
        PyObject *ele = PyList_GetItem(list, i);
        PyObject *attr;

        if (!ele)
            continue;

        iface_init_iface_t(&iface);

        /* initialize network configuration bits of loaderData struct */
        /* except for --device which we want to take over from cmdline */
        /* ksdevice for the first command */
        free(loaderData->ipv4);
        loaderData->ipv4 = NULL;
        loaderData->ipinfo_set = 0;
        free(loaderData->dns);
        loaderData->dns = NULL;
        free(loaderData->netmask);
        loaderData->netmask = NULL;
        free(loaderData->hostname);
        loaderData->hostname = NULL;
        free(loaderData->gateway);
        loaderData->gateway = NULL;
        free(loaderData->netCls);
        loaderData->netCls = NULL;
        loaderData->netCls_set = 0;
        free(loaderData->ethtool);
        loaderData->ethtool = NULL;
        loaderData->essid = NULL;
        free(loaderData->wepkey);
        loaderData->wepkey = NULL;
        free(loaderData->wpakey);
        loaderData->wpakey = NULL;
        loaderData->mtu = 0;

#ifdef ENABLE_IPV6
        free(loaderData->ipv6);
        loaderData->ipv6 = NULL;
        loaderData->ipv6info_set = 0;
        free(loaderData->gateway6);
        loaderData->gateway6 = NULL;
#endif

        /* if they've specified dhcp/bootp use dhcp for the interface */
        attr = getObject(ele, "bootProto", 0);
        if (objIsStr(attr, "dhcp") || objIsStr(attr, "bootp")) {
            loaderData->ipv4 = strdup("dhcp");
            loaderData->ipinfo_set = 1;
        } else if (objIsStr(attr, "ibft")) {
            loaderData->ipv4 = strdup("ibft");
            loaderData->ipinfo_set = 1;
        } else if (objIsStr(attr, "static")) {
            _setNetworkString(ele, "ip", &loaderData->ipv4, &loaderData->ipinfo_set);
        }

        Py_XDECREF(attr);

#ifdef ENABLE_IPV6
        _setNetworkString(ele, "ipv6", &loaderData->ipv6, &loaderData->ipv6info_set);
#endif

        _setNetworkString(ele, "nameserver", &loaderData->dns, NULL);
        _setNetworkString(ele, "netmask", &loaderData->netmask, NULL);
        _setNetworkString(ele, "hostname", &loaderData->hostname, NULL);

        /* --gateway is common for ipv4 and ipv6, same as in loader UI */
        attr = getObject(ele, "gateway", 0);
        if (isNotEmpty(attr)) {
            char *gateway = strdup(PyString_AsString(attr));
            if (isValidIPv4Address(gateway)) {
                loaderData->gateway = gateway;
#ifdef ENABLE_IPV6
            } else if (isValidIPv6Address(gateway)) {
                loaderData->gateway6 = gateway;
#endif
            } else {
                logMessage(WARNING,
                       "invalid address in kickstart --gateway");
                free(gateway);
            }
        }

        Py_XDECREF(attr);

        attr = getObject(ele, "device", 0);
        if (isNotEmpty(attr)) {
            char *device = PyString_AsString(attr);

            /* If --device=MAC was given, translate into a device name now. */
            if (index(device, ':') == NULL ||
                (loaderData->netDev = iface_mac2device(device)) == NULL)
                loaderData->netDev = strdup(device);

            loaderData->netDev_set = 1;
            logMessage(INFO, "kickstart network command - device %s", loaderData->netDev);
        } else {
            cmdline_device = strdup(loaderData->netDev);
            loaderData->netDev_set = 0;
            free(loaderData->netDev);
            loaderData->netDev = NULL;
            device_flushed = TRUE;
            logMessage(INFO, "kickstart network command - unspecified device");
        }

        Py_XDECREF(attr);

        _setNetworkString(ele, "dhcpclass", &loaderData->netCls, &loaderData->netCls_set);
        _setNetworkString(ele, "ethtool", &loaderData->ethtool, NULL);
        _setNetworkString(ele, "essid", &loaderData->essid, NULL);
        _setNetworkString(ele, "wepkey", &loaderData->wepkey, NULL);
        _setNetworkString(ele, "wpakey", &loaderData->wpakey, NULL);

        attr = getObject(ele, "noipv4", 0);
        if (isTrue(attr))
            flags |= LOADER_FLAGS_NOIPV4;

        Py_XDECREF(attr);

        attr = getObject(ele, "mtu", 0);
        if (isNotEmpty(attr)) {
            /* Don't free this string! */
            char *mtu = PyString_AsString(attr);

            errno = 0;
            loaderData->mtu = strtol(mtu, NULL, 10);

            if ((errno == ERANGE && (loaderData->mtu == LONG_MIN ||
                                     loaderData->mtu == LONG_MAX)) ||
                (errno != 0 && loaderData->mtu == 0)) {
                logMessage(ERROR, "%s: %d: %m", __func__, __LINE__);
                abort();
            }
        }

        Py_XDECREF(attr);

#ifdef ENABLE_IPV6
        attr = getObject(ele, "noipv6", 0);
        if (isTrue(attr))
            flags |= LOADER_FLAGS_NOIPV6;

        Py_XDECREF(attr);
#endif

        attr = getObject(ele, "nodns", 0);
        if (isTrue(attr))
            loaderData->noDns = 1;

        Py_XDECREF(attr);

        attr = getObject(ele, "nodefroute", 0);
        if (isTrue(attr))
            iface.defroute = 0;

        Py_XDECREF(attr);

        /* Always activate first network command device for network
         * installs(RHEL 5 behaviour) */
        if (!i &&
            (isURLRemote(loaderData->instRepo) ||
             FL_EARLY_NETWORKING(flags) ||
             ibft_present())) {
            logMessage(INFO, "activating first device from kickstart because network is needed");
            if (process_kickstart_wifi(loaderData) != 0) {
                if (device_flushed) {
                    loaderData->netDev = strdup(cmdline_device);
                    loaderData->netDev_set = 1;
                    free(cmdline_device);
                    cmdline_device = NULL;
                    device_flushed = FALSE;
                }
                activateDevice(loaderData, &iface);
            }
            continue;
        }

        attr = getObject(ele, "activate", 0);
        if (isTrue(attr)) {
            logMessage(INFO, "activating because --activate flag is set");
            if (process_kickstart_wifi(loaderData) != 0) {
                if (device_flushed) {
                    loaderData->netDev = strdup(cmdline_device);
                    loaderData->netDev_set = 1;
                    free(cmdline_device);
                    cmdline_device = NULL;
                    device_flushed = FALSE;
                }
                activateDevice(loaderData, &iface);
            }
        } else {
            logMessage(INFO, "not activating becuase --activate flag is not set");
        }

        Py_XDECREF(attr);
    }

    Py_XDECREF(list);
}

static void setKickstartCD(struct loaderData_s * loaderData, PyObject *handler) {
    PyObject *methodObj = getattr(handler, "method", "method");

    if (objIsStr(methodObj, "cdrom")) {
        logMessage(INFO, "kickstartFromCD");
        loaderData->method = METHOD_CDROM;
    }

    Py_XDECREF(methodObj);
}

static void setKickstartHD(struct loaderData_s * loaderData, PyObject *handler) {
    PyObject *methodObj = getattr(handler, "method", "method");
    PyObject *biospartObj = NULL;
    char *partition = NULL, *dir = NULL;

    if (!objIsStr(methodObj, "harddrive"))
        goto cleanup;

    logMessage(INFO, "kickstartFromHD");

    biospartObj = getattr(handler, "method", "biospart");
    if (isNotEmpty(biospartObj)) {
        char *biospart = strdup(PyString_AsString(biospartObj));
        char *dev, *p;

        p = strchr(biospart,'p');
        if(!p) {
            logMessage(ERROR, "Bad argument for --biospart");
            free(biospart);
            goto cleanup;
        }

        *p = '\0';
        dev = getBiosDisk(biospart);
        if (dev == NULL) {
            logMessage(ERROR, "Unable to location BIOS partition %s", biospart);
            free(biospart);
            goto cleanup;
        }

        partition = malloc(strlen(dev) + strlen(p + 1) + 2);
        sprintf(partition, "%s%s", dev, p + 1);
    }

    loaderData->method = METHOD_HD;

    if (!partition)
        partition = strdup(PyString_AsString(getattr(handler, "method", "partition")));

    dir = strdup(PyString_AsString(getattr(handler, "method", "dir")));

    checked_asprintf(&loaderData->instRepo, "hd:%s:%s", partition, dir);
    logMessage(INFO, "results of hd ks, partition is %s, dir is %s", partition,
               dir);

    free(partition);
    free(dir);
cleanup:
    Py_XDECREF(methodObj);
    Py_XDECREF(biospartObj);
}

static void setKickstartNfs(struct loaderData_s * loaderData, PyObject *handler) {
    PyObject *methodObj = getattr(handler, "method", "method");
    PyObject *hostObj = NULL, *dirObj = NULL, *optsObj = NULL;
    char *host, *dir;

    if (!objIsStr(methodObj, "nfs"))
        goto cleanup;

    logMessage(INFO, "kickstartFromNfs");

    hostObj = getattr(handler, "method", "server");
    dirObj = getattr(handler, "method", "dir");
    optsObj = getattr(handler, "method", "opts");

    if (!isNotEmpty(hostObj) || !isNotEmpty(dirObj)) {
        logMessage(ERROR, "host and directory for nfs kickstart not specified");
        goto cleanup;
    }

    /* Don't free these strings! */
    host = PyString_AsString(hostObj);
    dir = PyString_AsString(dirObj);

    loaderData->method = METHOD_NFS;

    if (isNotEmpty(optsObj)) {
        logMessage(INFO, "results of nfs, host is %s, dir is %s, opts are '%s'",
                   host, dir, PyString_AsString(optsObj));
        checked_asprintf(&loaderData->instRepo, "nfs:%s:%s:%s",
                         PyString_AsString(optsObj), host, dir);
    } else {
        logMessage(INFO, "results of nfs, host is %s, dir is %s", host, dir);
        checked_asprintf(&loaderData->instRepo, "nfs:%s:%s", host, dir);
    }

cleanup:
    Py_XDECREF(methodObj);
    Py_XDECREF(hostObj);
    Py_XDECREF(dirObj);
    Py_XDECREF(optsObj);
}

static void setKickstartUrl(struct loaderData_s * loaderData, PyObject *handler) {
    char *url = NULL;
    PyObject *methodObj = getattr(handler, "method", "method");
    PyObject *urlObj = NULL;
    PyObject *noverifysslObj = NULL, *proxyObj = NULL;

    if (!objIsStr(methodObj, "url"))
        goto cleanup;

    urlObj = getattr(handler, "method", "url");

    if (!isNotEmpty(urlObj))
        goto cleanup;

    /* Don't free this string! */
    url = PyString_AsString(urlObj);
    logMessage(INFO, "kickstartFromUrl");

    /* determine install type */
    if (strncmp(url, "http", 4) && strncmp(url, "ftp://", 6)) {
        newtWinMessage(_("Kickstart Error"), _("OK"),
                       _("Unknown Url method %s"), url);
        goto cleanup;
    }

    noverifysslObj = getattr(handler, "method", "noverifyssl");
    proxyObj = getattr(handler, "method", "proxy");

    loaderData->instRepo = strdup(url);
    loaderData->method = METHOD_URL;

    if (isTrue(noverifysslObj))
        loaderData->instRepo_noverifyssl = 1;
    else
        loaderData->instRepo_noverifyssl = 0;

    if (isNotEmpty(proxyObj)) {
        splitProxyParam(PyString_AsString(proxyObj), &loaderData->proxyUser,
                        &loaderData->proxyPassword,
                        &loaderData->proxy);
    }

    logMessage(INFO, "results of url ks, url %s", url);

cleanup:
    Py_XDECREF(methodObj);
    Py_XDECREF(urlObj);
    Py_XDECREF(noverifysslObj);
    Py_XDECREF(proxyObj);
}

char *runKickstart(struct loaderData_s * loaderData, const char *file) {
    PyObject *versionMod, *parserMod = NULL;
    PyObject *handler, *parser;
    PyObject *processedFile;
    char *retval = NULL;

    PyObject *callable = NULL;

    logMessage(INFO, "setting up kickstart");

    Py_Initialize();

    if ((versionMod = import("pykickstart.version")) == NULL)
        goto quit;

    if ((parserMod = import("pykickstart.parser")) == NULL)
        goto quit;

    if ((constantsMod = import("pykickstart.constants")) == NULL)
        goto quit;

    /* make the KickstartHandler object */
    if ((handler = makeHandler(versionMod)) == NULL)
        goto quit;

    /* make the KickstartParser object */
    if ((callable = getObject(parserMod, "KickstartParser", 1)) == NULL)
        goto quit;
    else
        parser = makeParser(callable, handler);

    /* call preprocessKickstart */
    processedFile = preprocessKickstart(parserMod, file);

    /* call readKickstart */
    if (processedFile) {
        commandFunc_t *cmd;

        if (!readKickstart(parser, processedFile))
            goto quit;

        /* Now handler is set up with all the kickstart data.  Run through
         * every element of the ksTable and run its function.  The functions
         * themselves will decide if they should do anything or not.
         */
        for (cmd = ksTable; *cmd != NULL; cmd++)
            (*cmd)(loaderData, handler);

        retval = strdup(PyString_AsString(processedFile));
    }

quit:
    Py_XDECREF(constantsMod);
    Py_XDECREF(versionMod);
    Py_XDECREF(callable);
    Py_XDECREF(parserMod);
    Py_Finalize();
    return retval;
}

/* vim:set sw=4 sts=4 et: */
